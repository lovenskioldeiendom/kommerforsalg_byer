"""
Scraper for "Kommer for salg"-prosjekter på Finn.

Søker per kommune via newbuildings/search.html med &sub_form_type=planned-filter.
"""

import argparse
import logging
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .config import (
    MUNICIPALITIES, USER_AGENT, DELAY_BETWEEN_REQUESTS_S, REQUEST_TIMEOUT_S,
)
from .parser import parse_planned_page, extract_planned_links_from_search
from .database import save_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def fetch(url: str):
    req = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "nb-NO,nb;q=0.9",
    })
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
            if resp.status != 200:
                logger.warning(f"HTTP {resp.status} for {url}")
                return None
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        logger.warning(f"HTTPError {e.code} for {url}")
        return None
    except (URLError, TimeoutError) as e:
        logger.warning(f"Network error for {url}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error for {url}: {e}")
        return None


def gather_planned_urls(municipality: dict) -> list[str]:
    """
    Henter planned-URLer ved å søke per kommune på search-siden.

    Vi bruker `sub_form_type=planned` for å filtrere bare på "Kommer for salg".
    """
    base = "https://www.finn.no/realestate/newbuildings/search.html"
    urls = set()
    page = 1
    max_pages = 10
    while page <= max_pages:
        url = (
            f"{base}?location={municipality['finn_location']}"
            f"&sub_form_type=planned&page={page}"
        )
        logger.info(f"[{municipality['name']}] søkeside {page}: {url}")
        html = fetch(url)
        if not html:
            break
        page_urls = extract_planned_links_from_search(html)
        if not page_urls:
            break
        new_count = len(set(page_urls) - urls)
        urls.update(page_urls)
        logger.info(f"[{municipality['name']}] side {page}: {len(page_urls)} lenker ({new_count} nye)")
        if new_count == 0:
            break
        page += 1
        time.sleep(DELAY_BETWEEN_REQUESTS_S)
    return sorted(urls)


def scrape_municipality(municipality: dict, dry_run: bool = False,
                        limit: int | None = None) -> dict:
    summary = {"municipality": municipality["name"], "found": 0, "scraped": 0, "errors": 0}

    project_urls = gather_planned_urls(municipality)
    summary["found"] = len(project_urls)
    logger.info(f"[{municipality['name']}] fant {len(project_urls)} kommer-for-salg-prosjekter")

    if limit:
        project_urls = project_urls[:limit]

    for i, url in enumerate(project_urls, 1):
        logger.info(f"[{municipality['name']}] {i}/{len(project_urls)}: {url}")
        html = fetch(url)
        if not html:
            summary["errors"] += 1
            continue

        try:
            project = parse_planned_page(
                html, source_url=url, municipality_hint=municipality["name"]
            )
        except Exception as e:
            logger.warning(f"Parse-feil for {url}: {e}")
            summary["errors"] += 1
            continue

        if not project.get("finn_code"):
            logger.info(f"[{municipality['name']}] mangler finn-kode, hopper over")
            continue

        if not dry_run:
            try:
                save_snapshot(municipality["name"], project, url)
            except Exception as e:
                logger.warning(f"DB-feil for {url}: {e}")
                summary["errors"] += 1
                continue

        summary["scraped"] += 1
        time.sleep(DELAY_BETWEEN_REQUESTS_S)

    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--municipality", default=None)
    args = parser.parse_args()

    municipalities = MUNICIPALITIES
    if args.municipality:
        municipalities = [m for m in MUNICIPALITIES
                         if m["name"].lower() == args.municipality.lower()]
        if not municipalities:
            logger.error(f"Ukjent kommune: {args.municipality}")
            sys.exit(1)

    overall = []
    for muni in municipalities:
        try:
            s = scrape_municipality(muni, dry_run=args.dry_run, limit=args.limit)
            overall.append(s)
        except Exception as e:
            logger.exception(f"Uventet feil for {muni['name']}: {e}")
            overall.append({"municipality": muni["name"], "error": str(e)})

    logger.info("━━━ OPPSUMMERING ━━━")
    for s in overall:
        logger.info(f"  {s}")


if __name__ == "__main__":
    main()
