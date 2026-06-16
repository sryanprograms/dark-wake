"""Phase 1 REST endpoints."""

from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from app.config.aoi import AOI_NAME, BBOX, DEFAULT_END, DEFAULT_START
from app.db.models import AisPosition, OperatorEvent, Vessel
from app.db.session import get_db
from app.ingest.cables import fetch_cables_in_bbox
from app.config.thresholds import REPLAY_DEFAULT_WINDOW_PRESET
from app.replay.clock import parse_time
from app.replay.window import compute_window

router = APIRouter()


def _bbox_from_query(
    min_lat: float | None,
    max_lat: float | None,
    min_lon: float | None,
    max_lon: float | None,
) -> dict[str, float]:
    if None in (min_lat, max_lat, min_lon, max_lon):
        return BBOX
    return {
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lon": min_lon,
        "max_lon": max_lon,
    }


@router.get("/assets/cables")
async def list_cables(
    min_lat: float | None = Query(default=None),
    max_lat: float | None = Query(default=None),
    min_lon: float | None = Query(default=None),
    max_lon: float | None = Query(default=None),
) -> dict:
    bbox = _bbox_from_query(min_lat, max_lat, min_lon, max_lon)
    try:
        with httpx.Client() as client:
            cables = fetch_cables_in_bbox(bbox, client=client)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"cable source unavailable: {exc}") from exc
    return {
        "source": "telegeography",
        "bbox": bbox,
        "count": len(cables),
        "cables": cables,
    }


@router.get("/scenarios")
async def list_scenarios(session: AsyncSession = Depends(get_db)) -> list[dict]:
    row = (
        await session.execute(select(func.min(AisPosition.t), func.max(AisPosition.t), func.count()))
    ).one()
    t_min, t_max, count = row[0], row[1], row[2]
    if count == 0:
        window_start, window_end = compute_window(
            parse_time(DEFAULT_START), parse_time(DEFAULT_END), REPLAY_DEFAULT_WINDOW_PRESET
        )
        return [
            {
                "id": AOI_NAME,
                "name": AOI_NAME,
                "bbox": BBOX,
                "start": window_start.astimezone(timezone.utc).isoformat(),
                "end": window_end.astimezone(timezone.utc).isoformat(),
                "data_start": DEFAULT_START,
                "data_end": DEFAULT_END,
                "window_preset": REPLAY_DEFAULT_WINDOW_PRESET,
                "position_count": 0,
                "loaded": False,
            }
        ]
    window_start, window_end = compute_window(t_min, t_max, REPLAY_DEFAULT_WINDOW_PRESET)
    return [
        {
            "id": AOI_NAME,
            "name": AOI_NAME,
            "bbox": BBOX,
            "start": window_start.astimezone(timezone.utc).isoformat(),
            "end": window_end.astimezone(timezone.utc).isoformat(),
            "data_start": t_min.astimezone(timezone.utc).isoformat(),
            "data_end": t_max.astimezone(timezone.utc).isoformat(),
            "window_preset": REPLAY_DEFAULT_WINDOW_PRESET,
            "position_count": count,
            "loaded": True,
        }
    ]


@router.get("/vessels/{mmsi}/track")
async def vessel_track(
    mmsi: int,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> dict:
    vessel = await session.get(Vessel, mmsi)

    query = (
        select(
            AisPosition.t.label("reported_at"),
            func.ST_Y(AisPosition.geom).label("lat"),
            func.ST_X(AisPosition.geom).label("lon"),
            AisPosition.sog,
            AisPosition.cog,
            AisPosition.heading,
        )
        .where(AisPosition.mmsi == mmsi)
        .order_by(AisPosition.t)
    )
    if start:
        query = query.where(AisPosition.t >= parse_time(start))
    if end:
        query = query.where(AisPosition.t <= parse_time(end))

    rows = (await session.execute(query)).all()
    if not rows:
        raise HTTPException(status_code=404, detail="vessel not found")

    return {
        "mmsi": mmsi,
        "name": vessel.name if vessel else None,
        "positions": [
            {
                "t": r._mapping["reported_at"].astimezone(timezone.utc).isoformat(),
                "lat": float(r.lat),
                "lon": float(r.lon),
                "sog": r.sog,
                "cog": r.cog,
                "heading": r.heading,
            }
            for r in rows
        ],
    }


@router.get("/events")
async def list_operator_events(
    limit: int = Query(default=50, ge=1, le=500),
    kind: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> dict:
    query = (
        select(OperatorEvent)
        .order_by(OperatorEvent.t.desc())
        .limit(limit)
    )
    if kind:
        query = query.where(OperatorEvent.kind == kind)

    rows = (await session.execute(query)).scalars().all()
    return {
        "count": len(rows),
        "events": [
            {
                "id": row.id,
                "kind": row.kind,
                "severity": row.severity,
                "mmsi": row.mmsi,
                "t": row.t.astimezone(timezone.utc).isoformat(),
                "title": row.title,
                "reason": row.reason,
                "details": row.details,
                "track_excerpt": row.track_excerpt,
            }
            for row in rows
        ],
    }
