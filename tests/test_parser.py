"""Tester for kommer-for-salg parser."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.parser import parse_planned_page, extract_planned_links_from_search

FIXTURES = Path(__file__).parent / "fixtures"


def test_no68_parsing():
    html = (FIXTURES / "no68_planned.html").read_text(encoding="utf-8")
    p = parse_planned_page(
        html,
        source_url="https://www.finn.no/realestate/planned/ad.html?finnkode=387771021",
        municipality_hint="Oslo",
    )

    assert p["finn_code"] == "387771021", f"finn_code={p['finn_code']}"
    assert "No68" in p["title"]
    assert p["address"] and "Thorvald Meyers" in p["address"], f"address={p['address']}"
    assert p["home_type"] == "Leilighet", f"home_type={p['home_type']}"
    assert p["bedrooms_range"] == "1 - 3", f"bedrooms_range={p['bedrooms_range']}"
    assert p["ownership"] == "Selveier", f"ownership={p['ownership']}"
    assert p["unit_count_hint"] == 18, f"unit_count_hint={p['unit_count_hint']}"
    assert p["sale_start"] and "4. kvartal 2025" in p["sale_start"], f"sale_start={p['sale_start']}"
    assert p["construction_start"] and "1. kvartal 2026" in p["construction_start"], f"construction_start={p['construction_start']}"
    assert p["handover"] and "3. kvartal 2027" in p["handover"], f"handover={p['handover']}"
    assert p["external_url"] == "https://bomer.no/prosjekt/thorvald-meyers-gate-68/"
    assert p["last_modified"] == "25. aug. 2025 13:50"

    print(f"✓ no68_parsing: {p['title']}, {p['unit_count_hint']} enheter, salgsstart {p['sale_start']}")


def test_search_extraction():
    html = (FIXTURES / "search_results.html").read_text(encoding="utf-8")
    urls = extract_planned_links_from_search(html)
    # Vi forventer 2 unike planned-URLer
    assert len(urls) == 2, f"Forventet 2 unike URLer, fikk {len(urls)}: {urls}"
    for u in urls:
        assert "/realestate/planned/ad.html" in u
        assert u.startswith("https://")
    print(f"✓ search_extraction: fant {len(urls)} unike planned-URLer")


if __name__ == "__main__":
    test_no68_parsing()
    test_search_extraction()
    print("\n✓ Alle tester passerer")
