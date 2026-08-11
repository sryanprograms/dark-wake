"""Tests for SAR loader clustering and persistence."""

from datetime import datetime, timezone

from app.config.thresholds import SCENE_CLUSTER_WINDOW_S
from app.ingest.sar_loader import (
    cluster_detections_into_scenes,
    load_sar_detections,
)


def test_cluster_by_shared_scene_id():
    detections = [
        {"t": "2022-06-10T16:00:00+00:00", "lat": 59.0, "lon": 24.0, "scene_id": "abc"},
        {"t": "2022-06-10T17:00:00+00:00", "lat": 59.1, "lon": 24.1, "scene_id": "abc"},
    ]
    scenes = cluster_detections_into_scenes(detections)
    assert len(scenes) == 1
    assert scenes[0]["scene_id"] == "abc"
    assert scenes[0]["detection_count"] == 2


def test_cluster_by_time_window_without_scene_id():
    detections = [
        {"t": "2022-06-10T16:00:00+00:00", "lat": 59.0, "lon": 24.0},
        {
            "t": "2022-06-10T16:20:00+00:00",
            "lat": 59.1,
            "lon": 24.1,
        },
    ]
    scenes = cluster_detections_into_scenes(detections, window_s=SCENE_CLUSTER_WINDOW_S)
    assert len(scenes) == 1
    assert scenes[0]["detection_count"] == 2


def test_cluster_splits_when_outside_window():
    gap_s = SCENE_CLUSTER_WINDOW_S + 60
    start = datetime(2022, 6, 10, 16, 0, tzinfo=timezone.utc)
    end = datetime.fromtimestamp(start.timestamp() + gap_s, tz=timezone.utc)
    detections = [
        {"t": start.isoformat(), "lat": 59.0, "lon": 24.0, "scene_id": "one"},
        {"t": end.isoformat(), "lat": 59.2, "lon": 24.2, "scene_id": "two"},
    ]
    scenes = cluster_detections_into_scenes(detections)
    assert len(scenes) == 2


def test_load_sar_detections_persists_scenes_and_points(db_conn, sample_sar_detections):
    counts = load_sar_detections(db_conn, sample_sar_detections, clear_existing=True)
    assert counts["detections"] == 3
    assert counts["scenes"] == 2

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sar_scene")
        scene_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sar_detection")
        detection_count = cur.fetchone()[0]

    assert scene_count == 2
    assert detection_count == 3


def test_load_sar_detections_upserts_without_duplicates(db_conn, sample_sar_detections):
    load_sar_detections(db_conn, sample_sar_detections, clear_existing=True)
    load_sar_detections(db_conn, sample_sar_detections, clear_existing=False)

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sar_detection")
        detection_count = cur.fetchone()[0]

    assert detection_count == 3


def test_load_sar_detections_dedupes_same_point_in_batch(db_conn):
    detections = [
        {"t": "2022-06-10T16:00:00+00:00", "lat": 55.0, "lon": 11.0, "scene_id": "a"},
        {"t": "2022-06-10T16:00:00+00:00", "lat": 55.0, "lon": 11.0, "scene_id": "a"},
    ]
    counts = load_sar_detections(db_conn, detections, clear_existing=True)
    assert counts["detections"] == 1

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sar_detection")
        assert cur.fetchone()[0] == 1
