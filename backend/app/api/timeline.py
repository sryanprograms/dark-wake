"""REST endpoints for the unified timeline: extent bounds and SAR scenes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.timeline.bounds import load_scenes, load_timeline_bounds

router = APIRouter(prefix="/timeline")


@router.get("/bounds")
async def timeline_bounds(session: AsyncSession = Depends(get_db)) -> dict:
    data_start, data_end, ais_count, scene_count = await load_timeline_bounds(session)
    return {
        "data_start": data_start.astimezone(timezone.utc).isoformat(),
        "data_end": data_end.astimezone(timezone.utc).isoformat(),
        "live_edge": datetime.now(timezone.utc).isoformat(),
        "ais_count": ais_count,
        "scene_count": scene_count,
    }


@router.get("/scenes")
async def timeline_scenes(session: AsyncSession = Depends(get_db)) -> list[dict]:
    return await load_scenes(session)
