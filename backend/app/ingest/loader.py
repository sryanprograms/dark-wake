"""Load normalized AIS positions into PostGIS."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import psycopg2
from psycopg2.extras import execute_values


def _parse_t(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def connect(database_url: str):
    return psycopg2.connect(database_url)


def load_positions(
    conn,
    positions: list[dict[str, Any]],
    *,
    clear_existing: bool = False,
) -> dict[str, int]:
    """Upsert vessels and bulk-insert AIS positions. Returns counts."""
    if clear_existing:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE ais_position, vessel RESTART IDENTITY CASCADE")
        conn.commit()

    vessels: dict[int, dict[str, object | None]] = {}
    for pos in positions:
        mmsi = int(pos["mmsi"])
        entry = vessels.setdefault(
            mmsi,
            {
                "name": None,
                "ship_type": None,
                "flag": None,
                "callsign": None,
                "imo": None,
            },
        )
        for field in ("name", "ship_type", "flag", "callsign", "imo"):
            value = pos.get(field)
            if value:
                entry[field] = value

    with conn.cursor() as cur:
        if vessels:
            execute_values(
                cur,
                """
                INSERT INTO vessel (mmsi, name, ship_type, flag, callsign, imo, updated_at)
                VALUES %s
                ON CONFLICT (mmsi) DO UPDATE SET
                    name = COALESCE(EXCLUDED.name, vessel.name),
                    ship_type = COALESCE(EXCLUDED.ship_type, vessel.ship_type),
                    flag = COALESCE(EXCLUDED.flag, vessel.flag),
                    callsign = COALESCE(EXCLUDED.callsign, vessel.callsign),
                    imo = COALESCE(EXCLUDED.imo, vessel.imo),
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    (
                        mmsi,
                        meta["name"],
                        meta["ship_type"],
                        meta["flag"],
                        meta["callsign"],
                        meta["imo"],
                        datetime.now(timezone.utc),
                    )
                    for mmsi, meta in vessels.items()
                ],
                template="(%s, %s, %s, %s, %s, %s, %s)",
            )

        rows = [
            (
                int(pos["mmsi"]),
                _parse_t(pos["t"]),
                float(pos["lon"]),
                float(pos["lat"]),
                pos.get("sog"),
                pos.get("cog"),
                pos.get("heading"),
            )
            for pos in positions
        ]
        if rows:
            execute_values(
                cur,
                """
                INSERT INTO ais_position (mmsi, t, geom, sog, cog, heading)
                VALUES %s
                """,
                rows,
                template=(
                    "(%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)"
                ),
            )
    conn.commit()
    return {"vessels": len(vessels), "positions": len(positions)}


def scenario_bounds(conn) -> dict[str, Any] | None:
    """Return min/max timestamps and position count, or None if empty."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MIN(t), MAX(t), COUNT(*), COUNT(DISTINCT mmsi)
            FROM ais_position
            """
        )
        row = cur.fetchone()
    if not row or row[2] == 0:
        return None
    t_min, t_max, count, vessels = row
    return {
        "start": t_min.astimezone(timezone.utc).isoformat(),
        "end": t_max.astimezone(timezone.utc).isoformat(),
        "position_count": count,
        "vessel_count": vessels,
    }
