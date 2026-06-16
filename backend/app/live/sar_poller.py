"""Background GFW SAR polling for live mode."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config.aoi import BBOX, GFW_QUERY_BBOX
from app.config.settings import Settings
from app.ingest.sar_gfw import fetch_detections

logger = logging.getLogger(__name__)


def _in_aoi(lat: float, lon: float) -> bool:
    return (
        BBOX["min_lat"] <= lat <= BBOX["max_lat"]
        and BBOX["min_lon"] <= lon <= BBOX["max_lon"]
    )


def _detection_key(det: dict) -> str:
    return f"{det.get('scene_id','')}:{det.get('t','')}:{det.get('lat')}:{det.get('lon')}"


async def poll_sar_detections(
    settings: Settings,
    *,
    since: datetime | None = None,
    seen: set[str] | None = None,
) -> tuple[list[dict], set[str]]:
    """Fetch recent SAR detections; return new ones not in `seen`."""
    if not settings.gfw_api_token:
        return [], seen or set()

    end = datetime.now(timezone.utc)
    start = since or (end - timedelta(days=7))
    seen_keys = seen or set()

    with httpx.Client() as client:
        detections = fetch_detections(
            GFW_QUERY_BBOX,
            start,
            end,
            client,
            token=settings.gfw_api_token,
        )

    new_detections: list[dict] = []
    for det in detections:
        lat = det.get("lat")
        lon = det.get("lon")
        if lat is None or lon is None or not _in_aoi(float(lat), float(lon)):
            continue
        key = _detection_key(det)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        new_detections.append(
            {
                "id": key,
                "t": det.get("t"),
                "lat": float(lat),
                "lon": float(lon),
                "length_m": det.get("length_m"),
                "confidence": det.get("confidence"),
                "scene_id": det.get("scene_id"),
            }
        )
    return new_detections, seen_keys
