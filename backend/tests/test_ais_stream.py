"""Tests for AISStream message parsing."""

from datetime import timezone

from app.ingest.ais_stream import (
    build_subscription_message,
    parse_aisstream_message,
    parse_position_report,
    parse_time_utc,
)


POSITION_FIXTURE = {
    "Message": {
        "PositionReport": {
            "Cog": 308,
            "Latitude": 59.95,
            "Longitude": 25.1,
            "Sog": 12.5,
            "TrueHeading": 235,
            "UserID": 259000420,
            "NavigationalStatus": 0,
        }
    },
    "MessageType": "PositionReport",
    "MetaData": {
        "MMSI": 259000420,
        "ShipName": "TESTSHIP",
        "latitude": 59.95,
        "longitude": 25.1,
        "time_utc": "2022-12-29 18:22:32.318353 +0000 UTC",
    },
}


def test_parse_time_utc():
    parsed = parse_time_utc("2022-12-29 18:22:32.318353 +0000 UTC")
    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
    assert parsed.year == 2022


def test_parse_position_report():
    result = parse_position_report(POSITION_FIXTURE)
    assert result is not None
    assert result["kind"] == "position"
    assert result["mmsi"] == 259000420
    assert result["lat"] == 59.95
    assert result["lon"] == 25.1
    assert result["sog"] == 12.5
    assert result["name"] == "TESTSHIP"


def test_parse_aisstream_message_dispatches():
    assert parse_aisstream_message(POSITION_FIXTURE) is not None
    assert parse_aisstream_message({"MessageType": "Unknown"}) is None


CLASS_B_FIXTURE = {
    "Message": {
        "StandardClassBPositionReport": {
            "Cog": 120.0,
            "Latitude": 55.5,
            "Longitude": 11.2,
            "Sog": 8.0,
            "TrueHeading": 118,
            "UserID": 219000123,
        }
    },
    "MessageType": "StandardClassBPositionReport",
    "MetaData": {
        "MMSI": 219000123,
        "ShipName": "CLASSB",
        "latitude": 55.5,
        "longitude": 11.2,
        "time_utc": "2022-12-29 18:22:32.318353 +0000 UTC",
    },
}


def test_parse_class_b_position_report():
    result = parse_aisstream_message(CLASS_B_FIXTURE)
    assert result is not None
    assert result["kind"] == "position"
    assert result["mmsi"] == 219000123
    assert result["lat"] == 55.5
    assert result["lon"] == 11.2


def test_build_subscription_message_shape():
    msg = build_subscription_message("  test-key  ")
    assert msg["APIKey"] == "test-key"
    assert len(msg["BoundingBoxes"]) == 1
    assert len(msg["BoundingBoxes"][0]) == 2
    assert "StandardClassBPositionReport" in msg["FilterMessageTypes"]
    assert "PositionReport" in msg["FilterMessageTypes"]
