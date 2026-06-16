"""Tests for AIS JSON loader."""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.ingest.json_loader import is_live_snapshot_payload, load_positions_from_json

BBOX = {"min_lat": 58.5, "max_lat": 60.3, "min_lon": 23.0, "max_lon": 27.0}


def test_is_live_snapshot_payload_detects_source():
    assert is_live_snapshot_payload({"source": "digitraffic-live"})
    assert not is_live_snapshot_payload({"source": "digitraffic-timestamped"})


def test_load_live_json_skips_historical_window_filter(tmp_path: Path):
    path = tmp_path / "live.json"
    path.write_text(
        json.dumps(
            {
                "source": "digitraffic-live",
                "live_snapshot": True,
                "positions": [
                    {
                        "mmsi": 111,
                        "t": "2026-06-15T12:00:00+00:00",
                        "lat": 59.5,
                        "lon": 24.5,
                        "name": "TEST SHIP",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    start = datetime(2022, 6, 1, tzinfo=timezone.utc)
    end = datetime(2022, 6, 30, tzinfo=timezone.utc)
    positions = load_positions_from_json(path, bbox=BBOX, start=start, end=end)
    assert len(positions) == 1
    assert positions[0]["name"] == "TEST SHIP"


def test_load_historical_json_applies_window_filter(tmp_path: Path):
    path = tmp_path / "hist.json"
    path.write_text(
        json.dumps(
            {
                "source": "digitraffic-timestamped",
                "positions": [
                    {
                        "mmsi": 111,
                        "t": "2026-06-15T12:00:00+00:00",
                        "lat": 59.5,
                        "lon": 24.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    start = datetime(2022, 6, 1, tzinfo=timezone.utc)
    end = datetime(2022, 6, 30, tzinfo=timezone.utc)
    positions = load_positions_from_json(path, bbox=BBOX, start=start, end=end)
    assert positions == []
