"""Tests for AIS position prediction at scene time."""

from datetime import datetime, timedelta, timezone

from app.fusion.predict import (
    dead_reckon,
    interpolate_position,
    predict_vessel_at,
)

T0 = datetime(2022, 6, 15, 12, 0, tzinfo=timezone.utc)


def _point(t_offset_s: int, lat: float, lon: float, sog: float = 10.0, cog: float = 90.0):
    return {
        "t": T0 + timedelta(seconds=t_offset_s),
        "lat": lat,
        "lon": lon,
        "sog": sog,
        "cog": cog,
    }


def test_interpolate_position_midpoint():
    points = [_point(0, 59.0, 24.0), _point(3600, 59.1, 24.1)]
    mid = interpolate_position(points, T0 + timedelta(seconds=1800))
    assert mid is not None
    assert abs(mid["lat"] - 59.05) < 1e-6
    assert abs(mid["lon"] - 24.05) < 1e-6


def test_interpolate_position_requires_bracketing():
    points = [_point(3600, 59.1, 24.1)]
    assert interpolate_position(points, T0) is None


def test_interpolate_position_exact_report():
    points = [_point(0, 59.0, 24.0), _point(3600, 59.1, 24.1)]
    exact = interpolate_position(points, T0)
    assert exact == {"lat": 59.0, "lon": 24.0}


def test_dead_reckon_projects_east_at_cog_90():
    last = _point(0, 59.0, 24.0, sog=10.0, cog=90.0)
    projected = dead_reckon(last, T0 + timedelta(hours=1))
    assert projected is not None
    assert abs(projected["lat"] - 59.0) < 0.001
    assert projected["lon"] > 24.0


def test_dead_reckon_stationary_without_sog():
    last = {"t": T0, "lat": 59.0, "lon": 24.0, "sog": 0.0, "cog": 90.0}
    projected = dead_reckon(last, T0 + timedelta(hours=1))
    assert projected == {"lat": 59.0, "lon": 24.0}


def test_dead_reckon_rejects_future_target():
    last = _point(0, 59.0, 24.0)
    assert dead_reckon(last, T0 - timedelta(seconds=1)) is None


def test_predict_vessel_at_observed():
    points = [_point(0, 59.0, 24.0)]
    result = predict_vessel_at(points, 123456789, T0)
    assert result is not None
    assert result["source"] == "observed"
    assert result["predicted"] is False
    assert result["mmsi"] == 123456789


def test_predict_vessel_at_interpolated():
    points = [_point(0, 59.0, 24.0), _point(3600, 59.1, 24.1)]
    result = predict_vessel_at(points, 123456789, T0 + timedelta(seconds=1800))
    assert result is not None
    assert result["source"] == "interpolated"
    assert result["predicted"] is True


def test_predict_vessel_at_dead_reckon_within_projection():
    points = [_point(0, 59.0, 24.0, sog=10.0, cog=90.0)]
    result = predict_vessel_at(points, 123456789, T0 + timedelta(hours=1), max_projection_s=7200)
    assert result is not None
    assert result["source"] == "dead_reckon"
    assert result["lon"] > 24.0


def test_predict_vessel_at_skips_beyond_max_projection():
    points = [_point(0, 59.0, 24.0)]
    result = predict_vessel_at(points, 123456789, T0 + timedelta(hours=3), max_projection_s=7200)
    assert result is None
