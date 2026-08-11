#!/usr/bin/env python3
"""Pull AIS positions for the configured AOI and date window."""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.aoi import AOI_NAME, BBOX, DEFAULT_END, DEFAULT_START  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.ingest.ais_csv import (  # noqa: E402
    filter_positions,
    load_positions_from_csv,
    load_positions_from_json,
    parse_dma_csv_text,
)
from app.ingest.digitraffic import fetch_digitraffic_positions  # noqa: E402

DMA_ZIP_URL = "https://web.ais.dk/aisdata/aisdk-{date}.zip"


def _parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def pull_digitraffic(
    client: httpx.Client,
    *,
    user_agent: str,
    bbox: dict[str, float],
    start: datetime | None,
    end: datetime | None,
    live_snapshot: bool = False,
) -> list[dict]:
    return fetch_digitraffic_positions(
        client,
        user_agent=user_agent,
        bbox=bbox,
        start=start,
        end=end,
        live_snapshot=live_snapshot,
    )

from app.ingest.digitraffic import fetch_digitraffic_positions  # noqa: E402


def pull_dma_day(
    client: httpx.Client,
    *,
    date: datetime,
    bbox: dict[str, float],
    start: datetime | None,
    end: datetime | None,
) -> list[dict]:
    url = DMA_ZIP_URL.format(date=date.strftime("%Y-%m-%d"))
    response = client.get(url, timeout=300.0, follow_redirects=True)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise RuntimeError(f"No CSV found in DMA archive {url}")
        text = zf.read(csv_names[0]).decode("utf-8", errors="replace")
    return parse_dma_csv_text(text, bbox, start, end)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull AIS positions for DarkWake Phase 0")
    parser.add_argument(
        "--source",
        choices=["digitraffic", "dma", "file"],
        default="dma",
        help="AIS data source (default: dma for Danish Belt / western Baltic)",
    )
    parser.add_argument("--start", default=DEFAULT_START, help="ISO start datetime (UTC)")
    parser.add_argument("--end", default=DEFAULT_END, help="ISO end datetime (UTC)")
    parser.add_argument("--file", dest="file_path", help="Path to CSV/JSON when --source file")
    parser.add_argument(
        "--format",
        choices=["dma", "baltic", "json"],
        default="json",
        help="File format when --source file",
    )
    parser.add_argument("--output", default=None, help="Output JSON path")
    parser.add_argument(
        "--live-snapshot",
        action="store_true",
        help="Digitraffic only: stamp all positions with current UTC time (spatial check only)",
    )
    args = parser.parse_args()

    settings = get_settings()
    start = _parse_dt(args.start)
    end = _parse_dt(args.end)
    out = Path(args.output) if args.output else Path(
        f"data/ais_{AOI_NAME}_{args.source}_{start.date()}_{end.date()}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client() as client:
        if args.source == "digitraffic":
            positions = pull_digitraffic(
                client,
                user_agent=settings.digitraffic_user,
                bbox=BBOX,
                start=start,
                end=end,
                live_snapshot=args.live_snapshot,
            )
            source_label = (
                "digitraffic-live" if args.live_snapshot else "digitraffic-timestamped"
            )
        elif args.source == "dma":
            positions = pull_dma_day(client, date=start, bbox=BBOX, start=start, end=end)
            source_label = "dma-historical"
        else:
            if not args.file_path:
                print("ERROR: --file is required when --source file", file=sys.stderr)
                return 1
            path = Path(args.file_path)
            if args.format == "json":
                positions = load_positions_from_json(path, bbox=BBOX, start=start, end=end)
            else:
                positions = load_positions_from_csv(
                    path, format=args.format, bbox=BBOX, start=start, end=end
                )
            source_label = f"file:{path.name}"

    payload = {
        "aoi": AOI_NAME,
        "bbox": BBOX,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "source": source_label,
        "count": len(positions),
        "positions": positions,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(positions)} AIS positions to {out}")
    if args.source == "digitraffic" and not args.live_snapshot:
        print(
            "NOTE: Digitraffic timestamps come from timestampExternal when available. "
            "For historical SAR windows, prefer --source file with a Baltic CSV."
        )
    elif args.source == "digitraffic":
        print(
            "NOTE: Live snapshot mode — positions stamped with current UTC. "
            "Use only when SAR window matches today."
        )
    return 0 if positions else 2


if __name__ == "__main__":
    raise SystemExit(main())
