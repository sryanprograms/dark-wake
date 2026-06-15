"""Tunable fusion and behavioral thresholds (spec §8–§9). Not used in Phase 0 logic."""

# Fusion (spec §8)
SAR_MATCH_RADIUS_M = 750
SAR_MATCH_TIME_WINDOW_S = 600
GAP_MIN_S = 900
DR_MAX_PROJECTION_S = 7200
SUSPICION_ASSET_BONUS = 0.3

# Asset behavioral layer (spec §9)
ASSET_PROXIMITY_M = 2000
LOITER_MAX_SOG_KN = 3.0
LOITER_MIN_DURATION_S = 1800
DRAG_SOG_MIN_KN = 0.5
DRAG_SOG_MAX_KN = 5.0
DRAG_MIN_TRACK_KM = 10

# Phase 0 overlap spike (looser than fusion; proves co-existence, not matching)
OVERLAP_TIME_MARGIN_S = 86400  # 24 h — Digitraffic timestampExternal is sparse
OVERLAP_MIN_AIS_POSITIONS = 1
