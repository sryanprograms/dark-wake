"""Scene-frame assembly via fusion.scene."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.fusion.scene import get_scene_frame
from app.db.models import Vessel

logger = logging.getLogger(__name__)


def _serialize_contacts(
    contacts: list[dict[str, Any]],
    ais: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map fusion contacts to the wire format expected by the frontend."""
    ais_by_mmsi = {int(v["mmsi"]): v for v in ais if v.get("mmsi") is not None}
    out: list[dict[str, Any]] = []
    for contact in contacts:
        mmsi = contact.get("matched_mmsi")
        matched = ais_by_mmsi.get(int(mmsi)) if mmsi is not None else None
        out.append(
            {
                "id": str(contact.get("sar_detection_id") or contact.get("id")),
                "kind": contact.get("classification") or contact.get("kind") or "dark",
                "sar_lat": contact.get("lat"),
                "sar_lon": contact.get("lon"),
                "ais_lat": matched.get("lat") if matched else None,
                "ais_lon": matched.get("lon") if matched else None,
                "mmsi": mmsi,
                "distance_m": contact.get("match_distance_m"),
                "confidence": contact.get("suspicion"),
                "reason": contact.get("reason"),
            }
        )
    return out


def _serialize_sar(sar: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(item.get("id", "")),
            "t": item.get("t"),
            "lat": item.get("lat"),
            "lon": item.get("lon"),
            "length_m": item.get("length_m"),
            "confidence": item.get("confidence"),
            "scene_id": item.get("scene_id"),
        }
        for item in sar
    ]


def _serialize_ais(ais: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "mmsi": int(v["mmsi"]),
            "t": v.get("ais_t") or v.get("t"),
            "lat": v["lat"],
            "lon": v["lon"],
            "sog": v.get("sog"),
            "cog": v.get("cog"),
            "heading": v.get("heading"),
            "name": v.get("name"),
            "ship_type": v.get("ship_type"),
            "flag": v.get("flag"),
            "country": v.get("country"),
        }
        for v in ais
        if v.get("mmsi") is not None and v.get("lat") is not None and v.get("lon") is not None
    ]


async def _enrich_ais_metadata(
    session: AsyncSession,
    ais: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    mmsis = [int(v["mmsi"]) for v in ais if v.get("mmsi") is not None]
    if not mmsis:
        return ais

    rows = (
        await session.execute(select(Vessel).where(Vessel.mmsi.in_(mmsis)))
    ).scalars().all()
    by_mmsi = {row.mmsi: row for row in rows}

    enriched: list[dict[str, Any]] = []
    for vessel in ais:
        mmsi = vessel.get("mmsi")
        meta = by_mmsi.get(int(mmsi)) if mmsi is not None else None
        enriched.append(
            {
                **vessel,
                "name": vessel.get("name") or (meta.name if meta else None),
                "ship_type": vessel.get("ship_type") or (meta.ship_type if meta else None),
                "flag": vessel.get("flag") or (meta.flag if meta else None),
            }
        )
    return enriched


async def build_scene_frame(session: AsyncSession, scene_id: int) -> dict:
    """Return a scene_frame payload for the given sar_scene id."""
    try:
        frame = await get_scene_frame(session, scene_id)
    except Exception:
        logger.exception("fusion.scene.get_scene_frame failed for scene_id=%s", scene_id)
        frame = {"t": None, "ais": [], "sar": [], "contacts": []}

    ais = _serialize_ais(await _enrich_ais_metadata(session, frame.get("ais", [])))
    sar = _serialize_sar(frame.get("sar", []))
    contacts = _serialize_contacts(frame.get("contacts", []), frame.get("ais", []))

    return {
        "type": "scene_frame",
        "scene_id": str(scene_id),
        "t": frame.get("t"),
        "ais": ais,
        "sar": sar,
        "contacts": contacts,
    }
