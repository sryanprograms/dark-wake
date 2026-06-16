#!/usr/bin/env python3
"""Load AIS JSON/CSV positions from Phase 0 pulls into PostGIS."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.aoi import BBOX, DEFAULT_END, DEFAULT_START  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.ingest.ais_csv import load_positions_from_csv, load_positions_from_json  # noqa: E402
from app.ingest.loader import connect, load_positions, scenario_bounds  # noqa: E402


def _parse_dt(value: str):
    from datetime import datetime, timezone

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load AIS positions into PostGIS")
    parser.add_argument("path", type=Path, help="AIS JSON or CSV file")
    parser.add_argument("--format", choices=("json", "dma", "baltic"), default="json")
    parser.add_argument("--clear", action="store_true", help="Truncate existing AIS data")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Skip historical window filter (for live snapshot / recording JSON)",
    )
    args = parser.parse_args()

    start = _parse_dt(DEFAULT_START)
    end = _parse_dt(DEFAULT_END)

    if args.format == "json":
        positions = load_positions_from_json(
            args.path, bbox=BBOX, start=start, end=end, live=args.live
        )
    else:
        positions = load_positions_from_csv(
            args.path, format=args.format, bbox=BBOX, start=start, end=end
        )

    if not positions:
        print("No positions to load for the configured AOI/window.", file=sys.stderr)
        return 1

    settings = get_settings()
    conn = connect(settings.database_url)
    try:
        counts = load_positions(conn, positions, clear_existing=args.clear)
        bounds = scenario_bounds(conn)
    finally:
        conn.close()

    print(f"Loaded {counts['positions']} positions for {counts['vessels']} vessels.")
    if bounds:
        print(f"Scenario window: {bounds['start']} → {bounds['end']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
