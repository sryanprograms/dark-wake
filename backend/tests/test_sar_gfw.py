"""Tests for GFW SAR detection client."""

from datetime import datetime, timezone

import httpx

from app.ingest.sar_gfw import fetch_detections, parse_report_response

BBOX = {"min_lat": 58.5, "max_lat": 60.3, "min_lon": 23.0, "max_lon": 27.0}


def test_parse_report_response_extracts_detections_in_bbox():
    payload = {
        "entries": [
            {
                "public-global-sar-presence:v3.0": [
                    {
                        "date": "2024-10-08 14:00",
                        "detections": 2,
                        "lat": 59.95,
                        "lon": 25.5,
                        "entryTimestamp": "2024-10-08T14:12:00Z",
                    },
                    {
                        "date": "2024-10-08 14:00",
                        "detections": 1,
                        "lat": 55.0,
                        "lon": 12.0,
                    },
                ]
            }
        ]
    }
    detections = parse_report_response(payload, BBOX)
    assert len(detections) == 1
    assert detections[0]["lat"] == 59.95
    assert detections[0]["lon"] == 25.5
    assert detections[0]["t"] == "2024-10-08T14:00:00+00:00"


def test_parse_report_response_handles_null_and_empty_rows():
    payload = {
        "entries": [
            {"public-global-sar-presence:v4.0": None},
            {
                "public-global-sar-presence:v3.0": [
                    None,
                    {"date": "2022-06-10 16:00", "lat": 58.92, "lon": 23.45, "detections": 1},
                    {"date": "2022-06-10 16:00", "lat": 55.0, "lon": 12.0, "detections": 1},
                ]
            },
        ]
    }
    detections = parse_report_response(payload, BBOX)
    assert len(detections) == 1
    assert detections[0]["lat"] == 58.92


def test_fetch_detections_uses_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "/v3/4wings/report" in str(request.url)
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(
            200,
            json={
                "entries": [
                    {
                        "public-global-sar-presence:v3.0": [
                            {
                                "date": "2024-10-08 10:00",
                                "detections": 1,
                                "lat": 60.0,
                                "lon": 24.0,
                            }
                        ]
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    start = datetime(2024, 10, 8, tzinfo=timezone.utc)
    end = datetime(2024, 10, 9, tzinfo=timezone.utc)

    detections = fetch_detections(
        BBOX,
        start,
        end,
        client,
        token="test-token",
    )
    assert len(detections) == 1
    assert detections[0]["lat"] == 60.0
