#!/usr/bin/env python3
"""Pull GFW SAR detections for the configured AOI and date window."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.aoi import AOI_NAME, BBOX, DEFAULT_END, DEFAULT_START  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.ingest.sar_gfw import fetch_detections  # noqa: E402


def _parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull GFW SAR detections for DarkWake Phase 0")
    parser.add_argument("--start", default=DEFAULT_START, help="ISO start datetime (UTC)")
    parser.add_argument("--end", default=DEFAULT_END, help="ISO end datetime (UTC)")
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path (default: data/sar_{aoi}_{date}.json)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.gfw_api_token:
        print("ERROR: GFW_API_TOKEN is not set. Add it to .env — see .env.example.", file=sys.stderr)
        return 1

    start = _parse_dt(args.start)
    end = _parse_dt(args.end)
    out = Path(args.output) if args.output else Path(
        f"data/sar_{AOI_NAME}_{start.date()}_{end.date()}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client() as client:
        detections = fetch_detections(
            BBOX,
            start,
            end,
            client,
            token=settings.gfw_api_token,
        )

    payload = {
        "aoi": AOI_NAME,
        "bbox": BBOX,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "source": "gfw",
        "count": len(detections),
        "detections": detections,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(detections)} SAR detections to {out}")
    return 0 if detections else 2


if __name__ == "__main__":
    raise SystemExit(main())
