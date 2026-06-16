"""Replay time-window helpers (default view vs full data extent)."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.config.thresholds import REPLAY_DEFAULT_WINDOW_PRESET, REPLAY_WINDOW_PRESETS

WindowPreset = str


def normalize_preset(value: str | None) -> WindowPreset:
    preset = (value or REPLAY_DEFAULT_WINDOW_PRESET).lower()
    if preset not in REPLAY_WINDOW_PRESETS:
        return REPLAY_DEFAULT_WINDOW_PRESET
    return preset


def compute_window(
    data_start: datetime,
    data_end: datetime,
    preset: WindowPreset | None = None,
) -> tuple[datetime, datetime]:
    """Return active replay bounds clamped to stored data."""
    key = normalize_preset(preset)
    span = REPLAY_WINDOW_PRESETS[key]
    window_end = data_end
    window_start = max(data_start, window_end - span)
    return window_start, window_end
