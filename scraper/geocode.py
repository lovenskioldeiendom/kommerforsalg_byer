"""Geocoding via OpenStreetMap Nominatim med SQLite-cache."""

import json
import logging
import time
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .database import get_cached_geocode, store_geocode, _NOT_FOUND, get_conn

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "kommer-for-salg-monitor/1.0 (github.com/kommer-for-salg)"
RATE_LIMIT_S = 1.1


def _query_nominatim(address: str):
    params = f"q={quote(address)}&format=json&limit=1&countrycodes=no"
    url = f"{NOMINATIM_URL}?{params}"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "nb"})
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data:
                return None
            r = data[0]
            return {
                "lat": float(r["lat"]),
                "lng": float(r["lon"]),
                "display_name": r.get("display_name", ""),
            }
    except (HTTPError, URLError, TimeoutError) as e:
        logger.warning(f"Nominatim-feil for '{address}': {e}")
        return None


def geocode_address(address: str):
    cached = get_cached_geocode(address)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    logger.info(f"  Geocoder: {address}")
    result = _query_nominatim(address)
    time.sleep(RATE_LIMIT_S)

    if result is None:
        store_geocode(address, None, None, None)
        return None

    store_geocode(address, result["lat"], result["lng"], result["display_name"])
    return result


def geocode_all_pending() -> dict:
    summary = {"total": 0, "already_cached": 0, "newly_geocoded": 0, "failed": 0}
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT DISTINCT s.address FROM snapshots s
            JOIN (
                SELECT finn_code, MAX(date) as max_date
                FROM snapshots GROUP BY finn_code
            ) latest ON s.finn_code = latest.finn_code AND s.date = latest.max_date
            WHERE s.address IS NOT NULL AND s.address != ''
        """).fetchall()

    addresses = [r["address"] for r in rows]
    summary["total"] = len(addresses)

    for addr in addresses:
        cached = get_cached_geocode(addr)
        if cached is not None:
            summary["already_cached"] += 1
            continue
        result = geocode_address(addr)
        if result:
            summary["newly_geocoded"] += 1
        else:
            summary["failed"] += 1

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    s = geocode_all_pending()
    logger.info(f"Geocoding ferdig: {s}")
