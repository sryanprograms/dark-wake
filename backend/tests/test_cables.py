"""Tests for submarine cable ingest."""

import httpx

from app.ingest import cables as cables_module
from app.ingest.cables import fetch_cables_in_bbox, parse_cable_features

BBOX = {"min_lat": 58.5, "max_lat": 60.3, "min_lon": 23.0, "max_lon": 27.0}

SAMPLE_PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "id": "c-lion1",
                "name": "C-Lion1",
                "color": "#7dc042",
            },
            "geometry": {
                "type": "MultiLineString",
                "coordinates": [
                    [
                        [23.2, 59.5],
                        [24.9, 60.1],
                    ],
                    [
                        [12.0, 54.0],
                        [13.0, 54.5],
                    ],
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "id": "far-away",
                "name": "Far Away Cable",
                "color": "#939597",
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [1.0, 40.0],
                    [2.0, 41.0],
                ],
            },
        },
    ],
}


def setup_function() -> None:
    cables_module._cache["features"] = []
    cables_module._cache["fetched_at"] = 0.0


def test_parse_cable_features_filters_by_bbox():
    parsed = parse_cable_features(SAMPLE_PAYLOAD, BBOX)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "C-Lion1"
    assert parsed[0]["path"][0] == [23.2, 59.5]
    assert parsed[0]["color"] == [125, 192, 66, 220]


def test_fetch_cables_in_bbox_uses_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(cables_module.TELEGEOGRAPHY_CABLE_GEO_URL)
        return httpx.Response(200, json=SAMPLE_PAYLOAD)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    cables = fetch_cables_in_bbox(BBOX, client=client)
    assert len(cables) == 1
    assert cables[0]["cable_id"] == "c-lion1"
