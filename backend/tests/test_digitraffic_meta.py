"""Tests for Digitraffic metadata enrichment."""

from app.ingest.digitraffic import enrich_positions_with_metadata


def test_enrich_positions_with_metadata():
    positions = [{"mmsi": 219598000, "lat": 59.9, "lon": 24.0, "t": "2022-06-17T04:00:00Z"}]
    metadata = {
        219598000: {
            "mmsi": 219598000,
            "name": "NORD SUPERIOR",
            "shipType": 80,
            "callSign": "OWPA2",
            "imo": 9692129,
        }
    }
    enrich_positions_with_metadata(positions, metadata)
    pos = positions[0]
    assert pos["name"] == "NORD SUPERIOR"
    assert pos["ship_type"] == "Tanker"
    assert pos["flag"] == "DK"
    assert pos["country"] == "Denmark"
    assert pos["callsign"] == "OWPA2"
    assert pos["imo"] == 9692129
