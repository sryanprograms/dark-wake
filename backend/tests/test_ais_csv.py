"""Tests for AIS CSV/JSON normalization."""

from datetime import datetime, timezone

from app.ingest.ais_csv import (
    normalize_baltic_row,
    normalize_dma_row,
    normalize_digitraffic_feature,
    parse_dma_csv_text,
)

BBOX = {"min_lat": 59.3, "max_lat": 60.3, "min_lon": 23.5, "max_lon": 27.0}


def test_normalize_dma_row_maps_expected_fields():
    row = {
        "Timestamp": "08/10/2024 12:34:56",
        "MMSI": "230123456",
        "Latitude": "59,95",
        "Longitude": "25,50",
        "SOG": "10.5",
        "COG": "180",
        "Heading": "175",
        "Name": "TEST SHIP",
    }
    pos = normalize_dma_row(row)
    assert pos is not None
    assert pos["mmsi"] == 230123456
    assert pos["lat"] == 59.95
    assert pos["lon"] == 25.5
    assert pos["sog"] == 10.5
    assert pos["name"] == "TEST SHIP"


def test_normalize_baltic_row_converts_speed_to_knots():
    row = {
        "timestamp": "2018-07-15T10:00:00Z",
        "mmsi": "123456789",
        "lat": "59.8",
        "lon": "24.2",
        "speed": "5.0",
        "course": "90",
        "heading": "88",
    }
    pos = normalize_baltic_row(row)
    assert pos is not None
    assert abs(pos["sog"] - 9.7192) < 0.01


def test_normalize_digitraffic_feature():
    feature = {
        "mmsi": 276000001,
        "geometry": {"coordinates": [25.1, 59.9]},
        "properties": {
            "mmsi": 276000001,
            "timestampExternal": 1728388800000,
            "sog": 12.3,
            "cog": 45.0,
            "heading": 44,
        },
    }
    pos = normalize_digitraffic_feature(feature)
    assert pos is not None
    assert pos["mmsi"] == 276000001
    assert pos["lat"] == 59.9
    assert pos["lon"] == 25.1


def test_parse_dma_csv_text_filters_to_bbox_and_window():
    csv_text = """Timestamp,Type of mobile,MMSI,Latitude,Longitude,Navigational status,ROT,SOG,COG,Heading,IMO,Callsign,Name,Ship type,Cargo type,Width,Length,Type of position fixing device,Draught,Destination,ETA,Data source type,A,B,C,D
08/10/2024 10:00:00,Class A,111111111,59.90,25.10,Under way,,5,90,88,,,IN,,,,,,,,,,,,
08/10/2024 10:05:00,Class A,222222222,55.00,12.00,Under way,,5,90,88,,,OUT,,,,,,,,,,,,
"""
    start = datetime(2024, 10, 8, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 10, 9, 0, 0, tzinfo=timezone.utc)
    positions = parse_dma_csv_text(csv_text, BBOX, start, end)
    assert len(positions) == 1
    assert positions[0]["mmsi"] == 111111111
