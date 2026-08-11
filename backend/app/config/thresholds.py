"""Tunable fusion, behavioral, and replay thresholds (spec §8–§9)."""

from datetime import timedelta

# Fusion (spec §8)
SAR_MATCH_RADIUS_M = 750
SAR_MATCH_TIME_WINDOW_S = 600
SCENE_CLUSTER_WINDOW_S = 1800
# AIS silence precursors (Tier 0) — not confirmed dark ships; see spec §8.
GAP_MIN_S = 1800  # 30 min — minimum silence before any live alert
GAP_HIGH_S = 3600  # 60 min — elevated severity / "suspicious" tier
DR_MAX_PROJECTION_S = 7200
SUSPICION_ASSET_BONUS = 0.3

# Asset behavioral layer (spec §9)
ASSET_PROXIMITY_M = 2000
LOITER_MAX_SOG_KN = 3.0
LOITER_MIN_DURATION_S = 1800
DRAG_SOG_MIN_KN = 0.5
DRAG_SOG_MAX_KN = 5.0
DRAG_MIN_TRACK_KM = 10

# Phase 1 replay (simulated seconds advanced per wall-clock tick)
REPLAY_SIM_SECONDS_PER_TICK = 3600  # 1 h — sparse historical AIS demos
REPLAY_DEFAULT_WINDOW_PRESET = "24h"
REPLAY_WINDOW_PRESETS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "3d": timedelta(days=3),
    "7d": timedelta(days=7),
}
TIMELINE_HISTORY_DAYS = 30  # scrubber + historical seek limited to this window
OVERLAP_TIME_MARGIN_S = 86400  # 24 h — Digitraffic timestampExternal is sparse
OVERLAP_MIN_AIS_POSITIONS = 1
