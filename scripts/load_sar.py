#!/usr/bin/env python3
"""Pull GFW SAR detections and load them into PostGIS."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.aoi import BBOX, DEFAULT_END, DEFAULT_START  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.db.migrate import run as run_migrations  # noqa: E402
from app.ingest.sar_gfw import fetch_detections  # noqa: E402
from app.ingest.sar_loader import connect, load_sar_detections, purge_sar_outside_bbox  # noqa: E402


def _parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _load_json_detections(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return list(payload.get("detections", []))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pull GFW SAR detections and load them into PostGIS"
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Optional pre-pulled SAR JSON (from pull_sar.py); skips GFW fetch",
    )
    parser.add_argument("--start", default=DEFAULT_START, help="ISO start datetime (UTC)")
    parser.add_argument("--end", default=DEFAULT_END, help="ISO end datetime (UTC)")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Truncate all SAR timeline tables before load",
    )
    parser.add_argument(
        "--purge-outside-aoi",
        action="store_true",
        default=True,
        help="Remove SAR rows outside the configured bbox (default: on)",
    )
    parser.add_argument(
        "--no-purge-outside-aoi",
        action="store_false",
        dest="purge_outside_aoi",
        help="Keep SAR detections outside the current bbox",
    )
    args = parser.parse_args()

    settings = get_settings()
    start = _parse_dt(args.start)
    end = _parse_dt(args.end)

    run_migrations()

    if args.file:
        detections = _load_json_detections(Path(args.file))
        if not detections:
            print(f"No detections in {args.file}", file=sys.stderr)
            return 2
    else:
        if not settings.gfw_api_token:
            print(
                "ERROR: GFW_API_TOKEN is not set. Add it to .env — see .env.example.",
                file=sys.stderr,
            )
            return 1
        with httpx.Client() as client:
            detections = fetch_detections(
                BBOX,
                start,
                end,
                client,
                token=settings.gfw_api_token,
            )
        if not detections:
            print("No SAR detections returned for the configured AOI/window.", file=sys.stderr)
            return 2

    conn = connect(settings.database_url)
    try:
        if args.purge_outside_aoi and not args.clear:
            purged = purge_sar_outside_bbox(conn, BBOX)
            if any(purged.values()):
                print(
                    f"Purged SAR outside AOI: {purged['detections']} detections, "
                    f"{purged['scenes']} scenes."
                )
        counts = load_sar_detections(conn, detections, clear_existing=args.clear)
    finally:
        conn.close()

    print(
        f"Loaded {counts['detections']} SAR detections across {counts['scenes']} scenes "
        f"({start.date()} → {end.date()})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
