"""Predict AIS vessel positions at an arbitrary (scene) time.

Given a vessel's observed AIS reports, estimate where it was at a target time
via exact lookup, linear interpolation between bracketing reports, or
dead-reckon projection past the last known report.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from app.config.thresholds import DR_MAX_PROJECTION_S
from app.fusion.time_util import ensure_utc

_KN_TO_MS = 0.514444
_M_PER_DEG_LAT = 111320.0


def _sorted_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(points, key=lambda p: ensure_utc(p["t"]))


def interpolate_position(
    points: list[dict[str, Any]],
    at: datetime,
) -> dict[str, float] | None:
    """Linear lat/lon interpolation at ``at`` between bracketing reports.

    Returns ``None`` when ``at`` is not bracketed by two reports (i.e. there is
    no report at/before and no report at/after).
    """
    if not points:
        return None

    at = ensure_utc(at)
    ordered = _sorted_points(points)

    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    for point in ordered:
        pt = ensure_utc(point["t"])
        if pt == at:
            return {"lat": point["lat"], "lon": point["lon"]}
        if pt < at:
            before = point
        elif after is None:
            after = point
            break

    if before is None or after is None:
        return None

    t0 = ensure_utc(before["t"])
    t1 = ensure_utc(after["t"])
    span = (t1 - t0).total_seconds()
    if span <= 0:
        return {"lat": before["lat"], "lon": before["lon"]}

    frac = (at - t0).total_seconds() / span
    return {
        "lat": before["lat"] + (after["lat"] - before["lat"]) * frac,
        "lon": before["lon"] + (after["lon"] - before["lon"]) * frac,
    }


def dead_reckon(last: dict[str, Any], at: datetime) -> dict[str, float] | None:
    """Project ``last`` forward to ``at`` along its course at its speed.

    Returns ``None`` if ``at`` precedes the last report. A zero/absent speed
    yields the unchanged position (stationary vessel).
    """
    at = ensure_utc(at)
    last_t = ensure_utc(last["t"])
    dt_s = (at - last_t).total_seconds()
    if dt_s < 0:
        return None

    sog = last.get("sog")
    if not sog:
        return {"lat": last["lat"], "lon": last["lon"]}

    cog_rad = math.radians(last.get("cog") or 0.0)
    dist_m = sog * _KN_TO_MS * dt_s
    dlat = dist_m * math.cos(cog_rad) / _M_PER_DEG_LAT
    lat = last["lat"]
    cos_lat = math.cos(math.radians(lat)) or 1e-9
    dlon = dist_m * math.sin(cog_rad) / (_M_PER_DEG_LAT * cos_lat)
    return {"lat": lat + dlat, "lon": last["lon"] + dlon}


def _carry(reference: dict[str, Any]) -> dict[str, Any]:
    return {
        "sog": reference.get("sog"),
        "cog": reference.get("cog"),
        "heading": reference.get("heading"),
        "name": reference.get("name"),
        "ship_type": reference.get("ship_type"),
        "flag": reference.get("flag"),
        "country": reference.get("country"),
    }


def predict_vessel_at(
    points: list[dict[str, Any]],
    mmsi: int,
    at: datetime,
    max_projection_s: float = DR_MAX_PROJECTION_S,
) -> dict[str, Any] | None:
    """Best estimate of a vessel's position at ``at``.

    Sources: ``observed`` (exact report), ``interpolated`` (between reports),
    or ``dead_reckon`` (projected past the last report, within
    ``max_projection_s``). Returns ``None`` when no estimate is possible.
    """
    if not points:
        return None

    at = ensure_utc(at)
    ordered = _sorted_points(points)
    first_t = ensure_utc(ordered[0]["t"])
    last = ordered[-1]
    last_t = ensure_utc(last["t"])

    if at < first_t:
        return None

    if at <= last_t:
        exact = next((p for p in ordered if ensure_utc(p["t"]) == at), None)
        if exact is not None:
            return {
                "mmsi": mmsi,
                "lat": exact["lat"],
                "lon": exact["lon"],
                "source": "observed",
                "predicted": False,
                "ais_t": at,
                **_carry(exact),
            }
        pos = interpolate_position(ordered, at)
        if pos is None:
            return None
        reference = next(p for p in reversed(ordered) if ensure_utc(p["t"]) < at)
        return {
            "mmsi": mmsi,
            "lat": pos["lat"],
            "lon": pos["lon"],
            "source": "interpolated",
            "predicted": True,
            "ais_t": at,
            **_carry(reference),
        }

    dt_s = (at - last_t).total_seconds()
    if dt_s > max_projection_s:
        return None
    pos = dead_reckon(last, at)
    if pos is None:
        return None
    return {
        "mmsi": mmsi,
        "lat": pos["lat"],
        "lon": pos["lon"],
        "source": "dead_reckon",
        "predicted": True,
        "ais_t": last_t,
        **_carry(last),
    }


def predict_vessels_at(
    tracks_by_mmsi: dict[int, list[dict[str, Any]]],
    at: datetime,
    max_projection_s: float = DR_MAX_PROJECTION_S,
) -> list[dict[str, Any]]:
    """Predict positions for every vessel track at ``at``, dropping misses."""
    predicted: list[dict[str, Any]] = []
    for mmsi, points in tracks_by_mmsi.items():
        estimate = predict_vessel_at(points, int(mmsi), at, max_projection_s=max_projection_s)
        if estimate is not None:
            predicted.append(estimate)
    return predicted
