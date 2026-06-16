#!/usr/bin/env python3
"""Record Digitraffic AIS polls to build replayable tracks over time."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.aoi import AOI_NAME, BBOX  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.ingest.digitraffic import fetch_digitraffic_positions  # noqa: E402
from app.ingest.loader import connect, load_positions  # noqa: E402

_stop = False


def _handle_signal(_signum, _frame) -> None:
    global _stop
    _stop = True


def _write_recording(path: Path, *, started_at: datetime, positions: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "aoi": AOI_NAME,
        "bbox": BBOX,
        "source": "digitraffic-recording",
        "live_snapshot": True,
        "started_at": started_at.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(positions),
        "positions": positions,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Poll Digitraffic and append AIS positions for replayable tracks"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Seconds between polls (default: 300 = 5 min)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Stop after N seconds (0 = until Ctrl+C)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"data/ais_{AOI_NAME}_recording.json"),
        help="Accumulated positions JSON",
    )
    parser.add_argument(
        "--to-db",
        action="store_true",
        help="Also append each poll into PostGIS (recommended for replay)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Truncate DB before first poll (with --to-db)",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    settings = get_settings()
    started_at = datetime.now(timezone.utc)
    all_positions: list[dict] = []
    poll = 0
    cleared = False
    deadline = time.time() + args.duration if args.duration > 0 else None

    print(
        f"Recording AIS every {args.interval}s for {AOI_NAME} "
        f"({'to DB + ' if args.to_db else ''}{args.output})"
    )

    while not _stop:
        poll += 1
        with httpx.Client() as client:
            batch = fetch_digitraffic_positions(
                client,
                user_agent=settings.digitraffic_user,
                bbox=BBOX,
                live_snapshot=True,
                enrich_metadata=True,
            )
        all_positions.extend(batch)
        print(
            f"[poll {poll}] {len(batch)} vessels "
            f"(total {len(all_positions)} positions, {len({p['mmsi'] for p in all_positions})} MMSIs)"
        )

        _write_recording(args.output, started_at=started_at, positions=all_positions)

        if args.to_db:
            conn = connect(settings.database_url)
            try:
                load_positions(
                    conn,
                    batch,
                    clear_existing=args.clear and not cleared,
                )
            finally:
                conn.close()
            cleared = True

        if deadline and time.time() >= deadline:
            break
        if _stop:
            break

        for _ in range(args.interval):
            if _stop:
                break
            time.sleep(1)

    print(f"Stopped. Saved {len(all_positions)} positions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
