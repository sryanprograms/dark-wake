"""Assemble a fused scene frame: SAR detections, predicted AIS, and contacts.

For a given ``sar_scene`` row, load its radar detections and the surrounding
AIS reports, predict each vessel's position at scene time, and classify every
detection as matched or dark.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.thresholds import DR_MAX_PROJECTION_S, SAR_MATCH_RADIUS_M, SAR_MATCH_TIME_WINDOW_S
from app.db.models import SarDetection, SarScene
from app.fusion.match import match_detections
from app.fusion.predict import predict_vessels_at
from app.replay.clock import parse_time
from app.replay.db_source import fetch_positions_between

logger = logging.getLogger(__name__)

# Look back far enough that a vessel that went silent before the scene can still
# be dead-reckoned forward; look ahead by the match window for interpolation.
_AIS_LOOKBACK = timedelta(seconds=max(DR_MAX_PROJECTION_S, 3 * 3600))
_AIS_LOOKAHEAD = timedelta(seconds=SAR_MATCH_TIME_WINDOW_S)


def _iso(t: datetime | None) -> str | None:
    if t is None:
        return None
    return t.astimezone(timezone.utc).isoformat()


async def _load_scene(session: AsyncSession, scene_id: int) -> SarScene | None:
    return await session.get(SarScene, scene_id)


async def _load_detections(session: AsyncSession, scene_key: str) -> list[dict[str, Any]]:
    stmt = (
        select(
            SarDetection.id,
            SarDetection.t,
            func.ST_Y(SarDetection.geom).label("lat"),
            func.ST_X(SarDetection.geom).label("lon"),
            SarDetection.length_m,
            SarDetection.confidence,
            SarDetection.scene_id,
        )
        .where(SarDetection.scene_id == scene_key)
        .order_by(SarDetection.id)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": row.id,
            "t": row.t,
            "lat": float(row.lat),
            "lon": float(row.lon),
            "length_m": row.length_m,
            "confidence": row.confidence,
            "scene_id": row.scene_id,
        }
        for row in rows
    ]


async def _load_tracks(
    session: AsyncSession,
    scene_t: datetime,
) -> dict[int, list[dict[str, Any]]]:
    start = scene_t - _AIS_LOOKBACK
    end = scene_t + _AIS_LOOKAHEAD
    events = await fetch_positions_between(session, start, end)
    tracks: dict[int, list[dict[str, Any]]] = {}
    for event in events:
        mmsi = event.get("mmsi")
        if mmsi is None:
            continue
        tracks.setdefault(int(mmsi), []).append({**event, "t": parse_time(event["t"])})
    return tracks


def build_scene_contacts(
    sar_detections: list[dict[str, Any]],
    predicted_ais: list[dict[str, Any]],
    scene_t: datetime,
    radius_m: float = SAR_MATCH_RADIUS_M,
) -> list[dict[str, Any]]:
    """Classify SAR detections against predicted AIS (package-level helper)."""
    return match_detections(sar_detections, predicted_ais, scene_t, radius_m=radius_m)


async def get_scene_frame(session: AsyncSession, scene_id: int) -> dict[str, Any]:
    """Return the fused frame for a ``sar_scene`` id.

    Shape: ``{"t", "ais", "sar", "contacts"}`` — JSON-serialisable, ready for
    the wire serializers in ``app.timeline.scene_frame``.
    """
    scene = await _load_scene(session, scene_id)
    if scene is None:
        logger.warning("get_scene_frame: no sar_scene with id=%s", scene_id)
        return {"t": None, "ais": [], "sar": [], "contacts": []}

    scene_t = scene.t.astimezone(timezone.utc)
    detections = await _load_detections(session, scene.scene_id)
    tracks = await _load_tracks(session, scene_t)
    predicted = predict_vessels_at(tracks, scene_t)

    contacts = build_scene_contacts(detections, predicted, scene_t)

    ais_out = [{**vessel, "ais_t": _iso(vessel.get("ais_t"))} for vessel in predicted]
    sar_out = [{**det, "t": _iso(det.get("t"))} for det in detections]
    contacts_out = [{**contact, "t": _iso(contact.get("t"))} for contact in contacts]

    return {
        "t": _iso(scene_t),
        "ais": ais_out,
        "sar": sar_out,
        "contacts": contacts_out,
    }
