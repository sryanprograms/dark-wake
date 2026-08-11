"""Tests for SAR-to-AIS fusion matching."""

from datetime import datetime, timezone

from app.fusion.match import haversine_m, match_detections

SCENE_T = datetime(2022, 6, 15, 12, 0, tzinfo=timezone.utc)


def test_haversine_m_same_point_is_zero():
    assert haversine_m(59.0, 24.0, 59.0, 24.0) == 0.0


def test_match_detections_one_matched_one_dark():
    sar_detections = [
        {"id": 1, "lat": 59.0, "lon": 24.0, "t": SCENE_T},
        {"id": 2, "lat": 61.0, "lon": 26.0, "t": SCENE_T},
    ]
    predicted_ais = [
        {
            "mmsi": 276000001,
            "lat": 59.0001,
            "lon": 24.0001,
            "predicted": False,
            "source": "observed",
            "ais_t": SCENE_T,
        }
    ]

    contacts = match_detections(sar_detections, predicted_ais, SCENE_T, radius_m=750)

    assert len(contacts) == 2
    matched = next(c for c in contacts if c["sar_detection_id"] == 1)
    dark = next(c for c in contacts if c["sar_detection_id"] == 2)

    assert matched["classification"] == "matched"
    assert matched["matched_mmsi"] == 276000001
    assert matched["match_distance_m"] is not None
    assert matched["match_distance_m"] < 750
    assert matched["predicted_from_gap"] is False
    assert "explains this radar return" in matched["reason"]

    assert dark["classification"] == "dark"
    assert dark["matched_mmsi"] is None
    assert dark["match_distance_m"] is None
    assert "No AIS vessel" in dark["reason"]


def test_match_detections_dead_reckon_match():
    sar_detections = [{"id": 3, "lat": 59.0, "lon": 24.05, "t": SCENE_T}]
    predicted_ais = [
        {
            "mmsi": 276000002,
            "lat": 59.0,
            "lon": 24.05,
            "predicted": True,
            "source": "dead_reckon",
            "ais_t": SCENE_T.replace(hour=10),
        }
    ]

    contacts = match_detections(sar_detections, predicted_ais, SCENE_T, radius_m=750)
    assert contacts[0]["classification"] == "matched"
    assert contacts[0]["predicted_from_gap"] is True
    assert "dead reckon" in contacts[0]["reason"]
