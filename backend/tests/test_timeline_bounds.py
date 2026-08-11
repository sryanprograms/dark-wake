"""Tests for timeline window clamping."""

from datetime import datetime, timedelta, timezone

from app.timeline.bounds import clamp_timeline_extent, timeline_window


def test_timeline_window_is_30_days():
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    start, end = timeline_window(now)
    assert end == now
    assert start == now - timedelta(days=30)


def test_clamp_timeline_extent_intersects_data_with_window():
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    t_min = datetime(2026, 6, 1, tzinfo=timezone.utc)
    t_max = datetime(2026, 6, 10, tzinfo=timezone.utc)
    start, end = clamp_timeline_extent(t_min, t_max, now=now)
    assert start == t_min
    assert end == t_max


def test_clamp_timeline_extent_cuts_old_data():
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    t_min = datetime(2024, 6, 1, tzinfo=timezone.utc)
    t_max = datetime(2024, 6, 10, tzinfo=timezone.utc)
    start, end = clamp_timeline_extent(t_min, t_max, now=now)
    assert start == now - timedelta(days=30)
    assert end == now


def test_clamp_timeline_extent_with_no_data_returns_window():
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    start, end = clamp_timeline_extent(None, None, now=now)
    assert start == now - timedelta(days=30)
    assert end == now
