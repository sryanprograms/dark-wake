"""Tests for track path grouping."""

from datetime import datetime, timezone

from app.replay.db_source import _row_to_event


class _FakeRow:
    def __init__(self, mapping: dict):
        self._mapping = mapping
        for k, v in mapping.items():
            setattr(self, k, v)


def test_row_to_event_includes_name():
    row = _FakeRow(
        {
            "mmsi": 123,
            "reported_at": datetime(2022, 6, 17, 4, 0, tzinfo=timezone.utc),
            "lat": 59.5,
            "lon": 24.0,
            "sog": 5.0,
            "cog": 90.0,
            "heading": 88.0,
            "name": "TESTER",
            "ship_type": "Tanker",
            "flag": "FI",
        }
    )
    event = _row_to_event(row)
    assert event["name"] == "TESTER"
    assert event["mmsi"] == 123
    assert event["ship_type"] == "Tanker"
    assert event["flag"] == "FI"


def test_row_to_event_derives_flag_from_mmsi_when_missing():
    row = _FakeRow(
        {
            "mmsi": 276000001,
            "reported_at": datetime(2022, 6, 17, 4, 0, tzinfo=timezone.utc),
            "lat": 59.5,
            "lon": 24.0,
            "sog": 5.0,
            "cog": 90.0,
            "heading": 88.0,
            "name": None,
            "ship_type": None,
            "flag": None,
        }
    )
    event = _row_to_event(row)
    assert event["flag"] == "EE"
    assert event["country"] == "Estonia"
