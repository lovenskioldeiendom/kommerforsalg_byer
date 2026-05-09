"""SQLite-lagring for kommer-for-salg-prosjekter."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "kommer-for-salg.db"


def _ensure_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            municipality TEXT NOT NULL,
            finn_code TEXT NOT NULL,
            title TEXT,
            subtitle TEXT,
            address TEXT,
            description TEXT,
            home_type TEXT,
            ownership TEXT,
            bedrooms_range TEXT,
            price_info TEXT,
            sale_start TEXT,
            construction_start TEXT,
            handover TEXT,
            stage TEXT,
            project_url TEXT,
            external_url TEXT,
            unit_count_hint INTEGER,
            last_modified TEXT,
            scraped_at TEXT NOT NULL,
            UNIQUE(date, finn_code)
        );

        CREATE TABLE IF NOT EXISTS geocode_cache (
            address TEXT PRIMARY KEY,
            lat REAL,
            lng REAL,
            display_name TEXT,
            geocoded_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_snap_date ON snapshots(date);
        CREATE INDEX IF NOT EXISTS idx_snap_muni ON snapshots(municipality);
        CREATE INDEX IF NOT EXISTS idx_snap_code ON snapshots(finn_code);
    """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_snapshot(municipality: str, project: dict, project_url: str) -> None:
    """Lagrer dagens snapshot for et planned-prosjekt."""
    today = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO snapshots
              (date, municipality, finn_code, title, subtitle, address,
               description, home_type, ownership, bedrooms_range, price_info,
               sale_start, construction_start, handover, stage,
               project_url, external_url, unit_count_hint, last_modified, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, finn_code) DO UPDATE SET
                title = excluded.title,
                subtitle = excluded.subtitle,
                address = excluded.address,
                description = excluded.description,
                home_type = excluded.home_type,
                ownership = excluded.ownership,
                bedrooms_range = excluded.bedrooms_range,
                price_info = excluded.price_info,
                sale_start = excluded.sale_start,
                construction_start = excluded.construction_start,
                handover = excluded.handover,
                stage = excluded.stage,
                project_url = excluded.project_url,
                external_url = excluded.external_url,
                unit_count_hint = excluded.unit_count_hint,
                last_modified = excluded.last_modified,
                scraped_at = excluded.scraped_at
        """, (
            today, municipality, project.get("finn_code"),
            project.get("title"), project.get("subtitle"),
            project.get("address"), project.get("description"),
            project.get("home_type"), project.get("ownership"),
            project.get("bedrooms_range"), project.get("price_info"),
            project.get("sale_start"), project.get("construction_start"),
            project.get("handover"), project.get("stage"),
            project_url, project.get("external_url"),
            project.get("unit_count_hint"), project.get("last_modified"),
            now,
        ))


def get_latest_snapshots() -> list[dict]:
    """Henter siste snapshot per prosjekt."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.* FROM snapshots s
            JOIN (
                SELECT finn_code, MAX(date) as max_date
                FROM snapshots GROUP BY finn_code
            ) latest ON s.finn_code = latest.finn_code AND s.date = latest.max_date
            ORDER BY s.municipality, s.title
        """).fetchall()
        return [dict(r) for r in rows]


def get_recent_changes(days_back: int = 30) -> dict:
    """
    Returnerer prosjekter som har endret status siste N dager:
    - 'new': Prosjekter som dukket opp i siste snapshot men ikke i baseline
    - 'gone': Prosjekter som var i baseline men borte nå (gått til salgs eller trukket)
    - 'updated': Prosjekter med endring i salgsstart, byggestart, handover, eller pris
    """
    with get_conn() as conn:
        latest_row = conn.execute(
            "SELECT MAX(date) FROM snapshots"
        ).fetchone()
        latest_date = latest_row[0] if latest_row else None
        if not latest_date:
            return {"new": [], "gone": [], "updated": []}

        target_date = conn.execute(
            "SELECT date(?, ?)", (latest_date, f"-{days_back} days")
        ).fetchone()[0]

        baseline_row = conn.execute("""
            SELECT date FROM snapshots
            WHERE date >= ? AND date < ?
            ORDER BY date ASC LIMIT 1
        """, (target_date, latest_date)).fetchone()
        if not baseline_row:
            baseline_row = conn.execute("""
                SELECT date FROM snapshots
                WHERE date < ?
                ORDER BY date DESC LIMIT 1
            """, (target_date,)).fetchone()
        if not baseline_row:
            return {"new": [], "gone": [], "updated": []}
        baseline_date = baseline_row[0]

        if baseline_date == latest_date:
            return {"new": [], "gone": [], "updated": []}

        baseline = {r["finn_code"]: dict(r) for r in conn.execute(
            "SELECT * FROM snapshots WHERE date = ?", (baseline_date,)
        ).fetchall()}
        current = {r["finn_code"]: dict(r) for r in conn.execute(
            "SELECT * FROM snapshots WHERE date = ?", (latest_date,)
        ).fetchall()}

        new = [c for code, c in current.items() if code not in baseline]
        gone = [b for code, b in baseline.items() if code not in current]

        updated = []
        for code, c in current.items():
            b = baseline.get(code)
            if not b:
                continue
            changes = []
            for field in ["sale_start", "construction_start", "handover",
                          "price_info", "stage"]:
                if (b.get(field) or "") != (c.get(field) or "") and c.get(field):
                    changes.append({
                        "field": field,
                        "old": b.get(field),
                        "new": c.get(field),
                    })
            if changes:
                updated.append({**c, "changes": changes, "since": baseline_date})

        return {"new": new, "gone": gone, "updated": updated}


# === Geocoding ===

def get_cached_geocode(address: str):
    """Returnerer dict med lat/lng, _NOT_FOUND, eller None."""
    if not address:
        return _NOT_FOUND
    with get_conn() as conn:
        row = conn.execute(
            "SELECT lat, lng FROM geocode_cache WHERE address = ?",
            (address,)
        ).fetchone()
        if row is None:
            return None
        if row["lat"] is None:
            return _NOT_FOUND
        return {"lat": row["lat"], "lng": row["lng"]}


def store_geocode(address: str, lat, lng, display_name) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO geocode_cache (address, lat, lng, display_name, geocoded_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(address) DO UPDATE SET
                lat = excluded.lat, lng = excluded.lng,
                display_name = excluded.display_name,
                geocoded_at = excluded.geocoded_at
        """, (address, lat, lng, display_name,
              datetime.now().isoformat(timespec="seconds")))


_NOT_FOUND = object()
