"""Match SAR detections against predicted AIS positions at scene time.

Each radar detection is paired with the nearest predicted AIS vessel within a
distance threshold. Unmatched detections are candidate "dark" ships.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from app.config.thresholds import SAR_MATCH_RADIUS_M
from app.fusion.time_util import ensure_utc

_EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two lat/lon points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _dt_seconds(detection_t: Any, ais_t: Any) -> float | None:
    if detection_t is None or ais_t is None:
        return None
    return abs((ensure_utc(detection_t) - ensure_utc(ais_t)).total_seconds())


def match_detections(
    sar_detections: list[dict[str, Any]],
    predicted_ais: list[dict[str, Any]],
    scene_t: datetime,
    radius_m: float = SAR_MATCH_RADIUS_M,
) -> list[dict[str, Any]]:
    """Classify each SAR detection as matched or dark against predicted AIS."""
    contacts: list[dict[str, Any]] = []

    for detection in sar_detections:
        det_lat = detection["lat"]
        det_lon = detection["lon"]
        det_t = detection.get("t", scene_t)

        best: dict[str, Any] | None = None
        best_dist = radius_m
        for vessel in predicted_ais:
            if vessel.get("lat") is None or vessel.get("lon") is None:
                continue
            dist = haversine_m(det_lat, det_lon, vessel["lat"], vessel["lon"])
            if dist <= best_dist:
                best_dist = dist
                best = vessel

        if best is not None:
            predicted_from_gap = bool(best.get("predicted")) and best.get("source") == "dead_reckon"
            if predicted_from_gap:
                reason = (
                    f"AIS vessel {best['mmsi']} (dead reckon projection) explains this "
                    "radar return"
                )
            else:
                reason = f"AIS vessel {best['mmsi']} explains this radar return"
            contacts.append(
                {
                    "sar_detection_id": detection.get("id"),
                    "classification": "matched",
                    "matched_mmsi": best["mmsi"],
                    "match_distance_m": best_dist,
                    "match_dt_s": _dt_seconds(det_t, best.get("ais_t")),
                    "predicted_from_gap": predicted_from_gap,
                    "suspicion": None,
                    "reason": reason,
                    "lat": det_lat,
                    "lon": det_lon,
                    "t": det_t,
                }
            )
        else:
            contacts.append(
                {
                    "sar_detection_id": detection.get("id"),
                    "classification": "dark",
                    "matched_mmsi": None,
                    "match_distance_m": None,
                    "match_dt_s": None,
                    "predicted_from_gap": False,
                    "suspicion": 1.0,
                    "reason": "No AIS vessel within match radius — candidate dark ship",
                    "lat": det_lat,
                    "lon": det_lon,
                    "t": det_t,
                }
            )

    return contacts
