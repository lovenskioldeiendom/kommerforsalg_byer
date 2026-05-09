"""
Parser for Finn.no "Kommer for salg"-annonser (URL: /realestate/planned/ad.html).

Annonsestrukturen er forskjellig fra "til salgs":
- Ingen detaljert enhetstabell
- I stedet: tidslinje med Planlegging / Salgsstart / Byggestart / Overtakelse
- Nøkkelinfo: Pris (ofte "Pris kommer"), Boligtype, Soverom-spenn, Eieform
- Lenke til prosjektets hjemmeside
"""

import re
from typing import Optional
from bs4 import BeautifulSoup


def _clean_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return re.sub(r"\s+", " ", text).strip() or None


def _extract_address(soup: BeautifulSoup) -> Optional[str]:
    """Adresselinjen — typisk en tekst med 4-sifret postnr."""
    for el in soup.find_all(["p", "div", "span", "address"]):
        text = el.get_text(" ", strip=True)
        if re.search(r"\b\d{4}\s+[A-ZÆØÅa-zæøå]", text) and 10 < len(text) < 200:
            text = re.sub(r"^Kart\s*", "", text)
            return _clean_text(text)
    return None


def _extract_finn_code(soup: BeautifulSoup, fallback_url: Optional[str] = None) -> str:
    # Tabell-rad
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2 and "finn-kode" in cells[0].get_text(strip=True).lower():
                code = re.sub(r"\D", "", cells[1].get_text())
                if code:
                    return code
    # Definition list
    for dt in soup.find_all("dt"):
        if "finn-kode" in dt.get_text(strip=True).lower():
            dd = dt.find_next_sibling("dd")
            if dd:
                code = re.sub(r"\D", "", dd.get_text())
                if code:
                    return code
    if fallback_url:
        m = re.search(r"finnkode=(\d+)", fallback_url)
        if m:
            return m.group(1)
    return ""


def _extract_last_modified(soup: BeautifulSoup) -> Optional[str]:
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2 and "sist endret" in cells[0].get_text(strip=True).lower():
                return _clean_text(cells[1].get_text())
    for dt in soup.find_all("dt"):
        if "sist endret" in dt.get_text(strip=True).lower():
            dd = dt.find_next_sibling("dd")
            if dd:
                return _clean_text(dd.get_text())
    return None


def _extract_keyinfo(soup: BeautifulSoup) -> dict:
    """
    Henter Pris, Boligtype, Soverom, Eieform fra Nøkkelinfo-seksjonen.

    Strukturen er typisk:
        <h2>Nøkkelinfo</h2>
        <dl> eller annen liste:
          Pris       Pris kommer
          Boligtype  Leilighet
          Soverom    1 - 3
          Eieform    Selveier
    """
    out = {
        "price_info": None,
        "home_type": None,
        "bedrooms_range": None,
        "ownership": None,
    }

    # Strategi 1: <dl> med <dt>/<dd>
    for dl in soup.find_all("dl"):
        for dt in dl.find_all("dt"):
            label = dt.get_text(strip=True).lower()
            dd = dt.find_next_sibling("dd")
            if not dd:
                continue
            value = _clean_text(dd.get_text())
            if "pris" in label and "kommer" not in label and out["price_info"] is None:
                out["price_info"] = value
            elif "boligtype" in label or "boligformat" in label:
                out["home_type"] = value
            elif "soverom" in label:
                out["bedrooms_range"] = value
            elif "eieform" in label:
                out["ownership"] = value

    # Strategi 2: tabell med to kolonner
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True).lower()
            value = _clean_text(cells[1].get_text())
            if not value:
                continue
            if label == "pris" and out["price_info"] is None:
                out["price_info"] = value
            elif label in ("boligtype", "boligformat") and out["home_type"] is None:
                out["home_type"] = value
            elif label == "soverom" and out["bedrooms_range"] is None:
                out["bedrooms_range"] = value
            elif label == "eieform" and out["ownership"] is None:
                out["ownership"] = value

    return out


def _extract_timeline(soup: BeautifulSoup) -> dict:
    """
    Henter tidslinjen: Planlegging / Salgsstart / Byggestart / Overtakelse.

    Strukturen er typisk en liste/grid med fire seksjoner.
    Hver har en label (h3/h4) og en tekst som "Antatt 4. kvartal 2025".
    """
    out = {
        "stage": None,           # Hvilken fase prosjektet er i
        "sale_start": None,
        "construction_start": None,
        "handover": None,
    }

    # Vi ser etter heading-tekster som "Salgsstart", "Byggestart", "Overtakelse",
    # "Planlegging" — og henter tekst som følger
    timeline_keywords = {
        "planlegging": "stage_planning",
        "salgsstart": "sale_start",
        "byggestart": "construction_start",
        "overtakelse": "handover",
        "innflytting": "handover",  # Synonym
    }

    # Strategi: gå gjennom alle headings og finn tekst etter dem
    for heading in soup.find_all(["h2", "h3", "h4", "strong", "b"]):
        label = heading.get_text(strip=True).lower()
        for kw, field in timeline_keywords.items():
            if kw in label and label != kw:
                continue  # Krev nøyaktig match
            if kw == label or label.startswith(kw):
                # Finn neste tekst — kan være neste sibling, eller barn av forelder
                value = None
                next_el = heading.find_next_sibling()
                if next_el:
                    value = _clean_text(next_el.get_text())
                if not value:
                    parent = heading.parent
                    if parent:
                        # Ta all tekst i parent etter heading
                        all_text = parent.get_text(" ", strip=True)
                        idx = all_text.lower().find(kw)
                        if idx >= 0:
                            after = all_text[idx + len(kw):].strip()
                            value = _clean_text(after)

                if value and value.lower() != kw:
                    if field == "stage_planning":
                        out["stage"] = value
                    else:
                        if not out[field]:
                            out[field] = value
                break

    return out


def _extract_external_url(soup: BeautifulSoup) -> Optional[str]:
    """Lenken til prosjektets hjemmeside."""
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if "prosjektets hjemmeside" in text or "prosjektside" in text:
            return a["href"]
    return None


def _extract_unit_count_hint(text: str) -> Optional[int]:
    """
    Forsøker å hente antall enheter fra tittel/beskrivelse.
    Eksempler: "18 unike leiligheter", "12 leiligheter", "8 boliger"
    """
    if not text:
        return None
    patterns = [
        r"(\d+)\s+(?:unike\s+)?(?:leiligheter|boliger|enheter|rekkehus|eneboliger|tomter)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                n = int(m.group(1))
                if 2 <= n <= 500:  # Rimelig spenn
                    return n
            except ValueError:
                pass
    return None


def parse_planned_page(html: str, source_url: Optional[str] = None,
                       municipality_hint: Optional[str] = None) -> dict:
    """Hovedfunksjon. Tar HTML, returnerer en dict med prosjektinfo."""
    soup = BeautifulSoup(html, "html.parser")

    # Tittel: h1
    title_el = soup.find("h1")
    title = _clean_text(title_el.get_text()) if title_el else "Ukjent prosjekt"

    # Undertittel: h2 nær h1
    subtitle = None
    if title_el:
        next_h = title_el.find_next(["h2", "h3"])
        if next_h:
            subtitle = _clean_text(next_h.get_text())

    # Beskrivelse: alt mellom "Beskrivelse"-heading og "Nyttige lenker"
    description = None
    desc_heading = None
    for h in soup.find_all(["h2", "h3"]):
        if "beskrivelse" in h.get_text(strip=True).lower():
            desc_heading = h
            break
    if desc_heading:
        chunks = []
        for sib in desc_heading.find_next_siblings():
            if sib.name in ["h2", "h3"]:
                break
            chunks.append(sib.get_text(" ", strip=True))
        description = _clean_text(" ".join(chunks))[:2000] if chunks else None

    address = _extract_address(soup)
    finn_code = _extract_finn_code(soup, fallback_url=source_url)
    last_modified = _extract_last_modified(soup)
    keyinfo = _extract_keyinfo(soup)
    timeline = _extract_timeline(soup)
    external_url = _extract_external_url(soup)

    # Unit count hint fra både tittel og beskrivelse
    unit_count_hint = (_extract_unit_count_hint(title or "")
                       or _extract_unit_count_hint(subtitle or "")
                       or _extract_unit_count_hint(description or ""))

    return {
        "finn_code": finn_code,
        "title": title,
        "subtitle": subtitle,
        "address": address,
        "description": description,
        "municipality": municipality_hint,
        "last_modified": last_modified,
        "external_url": external_url,
        "unit_count_hint": unit_count_hint,
        **keyinfo,
        **timeline,
    }


def extract_planned_links_from_search(html: str) -> list[str]:
    """
    Fra en Finn-søkeside, returnerer alle URLer som peker til /realestate/planned/.
    """
    soup = BeautifulSoup(html, "html.parser")
    urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/realestate/planned/ad.html" in href and "finnkode=" in href:
            if href.startswith("/"):
                href = "https://www.finn.no" + href
            urls.add(href)
    return sorted(urls)
