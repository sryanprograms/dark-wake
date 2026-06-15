"""Tests for Phase 0 overlap spike logic."""

from datetime import datetime, timezone

from app.config.aoi import BBOX
from app.spike_overlap import check_overlap, format_report

START = datetime(2024, 10, 8, 8, 0, tzinfo=timezone.utc)
END = datetime(2024, 10, 8, 20, 0, tzinfo=timezone.utc)


def _ais(t_hour: int, mmsi: int = 1) -> dict:
    t = datetime(2024, 10, 8, t_hour, 0, tzinfo=timezone.utc).isoformat()
    return {"mmsi": mmsi, "t": t, "lat": 59.9, "lon": 25.1}


def _sar(hour: int, minute: int = 30) -> dict:
    t = datetime(2024, 10, 8, hour, minute, tzinfo=timezone.utc).isoformat()
    return {"t": t, "lat": 59.95, "lon": 25.2, "detections": 1}


def test_overlap_passes_when_sar_scene_inside_ais_window():
    ais = [_ais(h) for h in range(8, 21) for _ in range(2)]
    sar = [_sar(14, 30), _sar(16, 0)]
    report = check_overlap(
        bbox=BBOX,
        ais_positions=ais,
        sar_detections=sar,
        ais_source="test",
        min_ais_positions=5,
    )
    assert report.overlap is True
    assert report.overlapping_scene_time is not None
    assert "PASS" in format_report(report)


def test_overlap_fails_when_sar_scene_outside_ais_window():
    ais = [_ais(h) for h in range(8, 13)]
    sar = [_sar(18, 0)]
    report = check_overlap(
        bbox=BBOX,
        ais_positions=ais,
        sar_detections=sar,
        ais_source="test",
        time_margin_s=3600,
        min_ais_positions=5,
    )
    assert report.overlap is False
    assert report.overlapping_scene_time is None
    assert any("AIS coverage window" in r for r in report.reasons)
