"""Tests for replay window presets."""

from datetime import datetime, timedelta, timezone

from app.replay.window import compute_window, normalize_preset

DATA_START = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
DATA_END = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


def test_compute_window_default_24h_anchors_to_data_end():
    start, end = compute_window(DATA_START, DATA_END, "24h")
    assert end == DATA_END
    assert start == DATA_END - timedelta(hours=24)


def test_compute_window_3d_and_7d():
    start_3d, end_3d = compute_window(DATA_START, DATA_END, "3d")
    assert end_3d == DATA_END
    assert start_3d == DATA_END - timedelta(days=3)

    start_7d, end_7d = compute_window(DATA_START, DATA_END, "7d")
    assert end_7d == DATA_END
    assert start_7d == DATA_END - timedelta(days=7)


def test_compute_window_clamps_when_data_span_is_shorter_than_preset():
    short_end = DATA_START + timedelta(hours=6)
    start, end = compute_window(DATA_START, short_end, "24h")
    assert start == DATA_START
    assert end == short_end


def test_normalize_preset_falls_back_to_default():
    assert normalize_preset("24h") == "24h"
    assert normalize_preset("bad") == "24h"
    assert normalize_preset(None) == "24h"
