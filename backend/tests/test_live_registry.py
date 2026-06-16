"""Tests for live vessel registry."""

from datetime import datetime, timedelta, timezone

from app.live.registry import VesselRegistry


def _pos(mmsi: int, minute: int, lat: float = 59.9, lon: float = 25.0) -> dict:
    return {
        "kind": "position",
        "mmsi": mmsi,
        "t": datetime(2026, 6, 15, 12, minute, tzinfo=timezone.utc),
        "lat": lat,
        "lon": lon,
        "sog": 10.0,
        "cog": 90.0,
        "heading": 90.0,
        "name": "TESTER",
        "flag": "FI",
        "country": "Finland",
    }


def test_registry_snapshot_and_tracks():
    reg = VesselRegistry(track_max_age=timedelta(hours=6))
    reg.apply_position(_pos(123, 0))
    reg.apply_position(_pos(123, 5))
    reg.apply_position(_pos(456, 1, lat=60.0, lon=26.0))

    snapshot = reg.snapshot()
    assert len(snapshot) == 2
    assert snapshot[0]["type"] == "ais"

    tracks = reg.tracks()
    assert len(tracks) == 1
    assert tracks[0]["mmsi"] == 123
    assert len(tracks[0]["path"]) == 2


def test_registry_prunes_old_track_points():
    reg = VesselRegistry(track_max_age=timedelta(minutes=30))
    now = datetime.now(timezone.utc)
    old = _pos(123, 0)
    old["t"] = now - timedelta(hours=2)
    recent = _pos(123, 5)
    recent["t"] = now - timedelta(minutes=5)
    reg.apply_position(old)
    reg.apply_position(recent)
    state = reg.get(123)
    assert state is not None
    assert len(state.track) == 1
