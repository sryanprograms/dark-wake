#!/usr/bin/env python3
"""Run the full Phase 0 overlap gate (pull AIS + SAR, then spike)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> int:
    print(f"\n$ {' '.join(cmd)}\n")
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DarkWake Phase 0 overlap gate end-to-end")
    parser.add_argument("--start", default="2022-06-01T00:00:00Z")
    parser.add_argument("--end", default="2022-06-30T00:00:00Z")
    parser.add_argument(
        "--ais-source",
        choices=["digitraffic", "dma", "file"],
        default="digitraffic",
    )
    parser.add_argument("--ais-file", help="Required when --ais-source file")
    parser.add_argument("--ais-format", choices=["dma", "baltic", "json"], default="baltic")
    args = parser.parse_args()

    py = sys.executable
    sar_out = ROOT / "data" / f"sar_gulf_of_finland_{args.start[:10]}_{args.end[:10]}.json"
    ais_out = ROOT / "data" / f"ais_gulf_of_finland_{args.ais_source}_{args.start[:10]}_{args.end[:10]}.json"

    sar_cmd = [
        py,
        str(ROOT / "scripts" / "pull_sar.py"),
        "--start",
        args.start,
        "--end",
        args.end,
        "--output",
        str(sar_out),
    ]
    if _run(sar_cmd) != 0:
        return 1

    ais_cmd = [
        py,
        str(ROOT / "scripts" / "pull_ais.py"),
        "--source",
        args.ais_source,
        "--start",
        args.start,
        "--end",
        args.end,
        "--output",
        str(ais_out),
    ]
    if args.ais_source == "file":
        if not args.ais_file:
            print("ERROR: --ais-file required for file source", file=sys.stderr)
            return 1
        ais_cmd.extend(["--file", args.ais_file, "--format", args.ais_format])

    if _run(ais_cmd) != 0:
        return 1

    spike_cmd = [
        py,
        str(ROOT / "scripts" / "spike_overlap.py"),
        "--ais",
        str(ais_out),
        "--sar",
        str(sar_out),
    ]
    return _run(spike_cmd)


if __name__ == "__main__":
    raise SystemExit(main())
