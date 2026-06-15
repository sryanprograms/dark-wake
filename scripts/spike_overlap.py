#!/usr/bin/env python3
"""Phase 0 gate: confirm AIS and SAR overlap for the chosen AOI/window."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.aoi import BBOX  # noqa: E402
from app.spike_overlap import check_overlap, format_report  # noqa: E402


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="DarkWake Phase 0 overlap spike")
    parser.add_argument("--ais", required=True, help="AIS JSON file from pull_ais.py")
    parser.add_argument("--sar", required=True, help="SAR JSON file from pull_sar.py")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON report")
    args = parser.parse_args()

    ais_data = _load_json(Path(args.ais))
    sar_data = _load_json(Path(args.sar))

    report = check_overlap(
        bbox=BBOX,
        ais_positions=ais_data.get("positions", []),
        sar_detections=sar_data.get("detections", []),
        ais_source=ais_data.get("source", "unknown"),
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(format_report(report))

    return 0 if report.overlap else 1


if __name__ == "__main__":
    raise SystemExit(main())
