"""Phase C fusion core — AIS prediction and SAR matching at scene time."""

from app.fusion.match import haversine_m, match_detections
from app.fusion.predict import (
    dead_reckon,
    interpolate_position,
    predict_vessel_at,
    predict_vessels_at,
)
from app.fusion.scene import build_scene_contacts, get_scene_frame

__all__ = [
    "build_scene_contacts",
    "dead_reckon",
    "get_scene_frame",
    "haversine_m",
    "interpolate_position",
    "match_detections",
    "predict_vessel_at",
    "predict_vessels_at",
]
