#!/usr/bin/env python3
"""Pull Digitraffic live AIS snapshot and load into PostGIS (dense corridor traffic)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.aoi import AOI_NAME, BBOX  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.ingest.digitraffic import fetch_digitraffic_positions  # noqa: E402
from app.ingest.loader import connect, load_positions, scenario_bounds  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pull live Digitraffic AIS for the AOI and load into PostGIS"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"data/ais_{AOI_NAME}_live.json"),
        help="Also save pulled JSON here",
    )
    parser.add_argument("--clear", action="store_true", help="Truncate existing AIS data")
    parser.add_argument("--pull-only", action="store_true", help="Pull JSON only, skip DB load")
    args = parser.parse_args()

    settings = get_settings()
    with httpx.Client() as client:
        positions = fetch_digitraffic_positions(
            client,
            user_agent=settings.digitraffic_user,
            bbox=BBOX,
            live_snapshot=True,
            enrich_metadata=True,
        )

    if not positions:
        print("No vessels in AOI from Digitraffic.", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "aoi": AOI_NAME,
        "bbox": BBOX,
        "source": "digitraffic-live",
        "live_snapshot": True,
        "pulled_at": now.isoformat(),
        "count": len(positions),
        "positions": positions,
    }
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(positions)} positions to {args.output}")

    if args.pull_only:
        return 0

    conn = connect(settings.database_url)
    try:
        counts = load_positions(conn, positions, clear_existing=args.clear)
        bounds = scenario_bounds(conn)
    finally:
        conn.close()

    print(f"Loaded {counts['positions']} positions for {counts['vessels']} vessels into PostGIS.")
    if bounds:
        print(f"Scenario window: {bounds['start']} → {bounds['end']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
