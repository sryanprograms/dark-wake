"""Tests for AIS silence precursor detection."""

from datetime import datetime, timedelta, timezone

from app.live.detect import detect_ais_gap_resume, detect_ais_silent
from app.live.registry import PositionPoint, VesselState


def test_detect_ais_gap_resume_after_threshold():
    state = VesselState(mmsi=123, name="TESTER", gap_monitor=True)
    state.latest = PositionPoint(
        t=datetime(2026, 6, 15, 13, 0, tzinfo=timezone.utc),
        lat=59.9,
        lon=25.0,
    )
    previous = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    current = datetime(2026, 6, 15, 13, 0, tzinfo=timezone.utc)

    alert = detect_ais_gap_resume(state, previous_at=previous, current_at=current)
    assert alert is not None
    assert alert["kind"] == "ais_gap_resume"
    assert alert["tier"] == "suspicious"
    assert alert["mmsi"] == 123


def test_no_gap_alert_under_threshold():
    state = VesselState(mmsi=123, gap_monitor=True)
    state.latest = PositionPoint(
        t=datetime(2026, 6, 15, 12, 20, tzinfo=timezone.utc),
        lat=59.9,
        lon=25.0,
    )
    previous = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    current = datetime(2026, 6, 15, 12, 20, tzinfo=timezone.utc)
    assert detect_ais_gap_resume(state, previous_at=previous, current_at=current) is None


def test_no_gap_alert_without_monitoring():
    state = VesselState(mmsi=123, gap_monitor=False)
    previous = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    current = datetime(2026, 6, 15, 13, 30, tzinfo=timezone.utc)
    assert detect_ais_gap_resume(state, previous_at=previous, current_at=current) is None


def test_detect_ais_silent():
    state = VesselState(mmsi=456, name="QUIET", gap_monitor=True)
    last_seen = datetime.now(timezone.utc) - timedelta(minutes=45)
    state.last_ingest_at = last_seen
    state.latest = PositionPoint(t=last_seen, lat=59.8, lon=24.5)
    alert = detect_ais_silent(state, now=datetime.now(timezone.utc))
    assert alert is not None
    assert alert["kind"] == "ais_silent"
    assert alert["tier"] == "suspicious"
    assert alert["severity"] == "high"
