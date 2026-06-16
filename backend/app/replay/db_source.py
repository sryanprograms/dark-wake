"""Query AIS positions from PostGIS for replay."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AisPosition, Vessel
from app.ingest.vessel_meta import country_from_mmsi, flag_from_mmsi


def _row_to_event(row) -> dict:
    reported_at = row._mapping["reported_at"]
    mmsi = row.mmsi
    flag = row._mapping.get("flag") or flag_from_mmsi(mmsi)
    country = row._mapping.get("country") or country_from_mmsi(mmsi)
    return {
        "type": "ais",
        "mmsi": mmsi,
        "t": reported_at.astimezone(timezone.utc).isoformat(),
        "lat": float(row.lat),
        "lon": float(row.lon),
        "sog": row.sog,
        "cog": row.cog,
        "heading": row.heading,
        "name": row._mapping.get("name"),
        "ship_type": row._mapping.get("ship_type"),
        "flag": flag,
        "country": country,
    }


def _position_select():
    return select(
        AisPosition.mmsi,
        AisPosition.t.label("reported_at"),
        func.ST_Y(AisPosition.geom).label("lat"),
        func.ST_X(AisPosition.geom).label("lon"),
        AisPosition.sog,
        AisPosition.cog,
        AisPosition.heading,
        Vessel.name,
        Vessel.ship_type,
        Vessel.flag,
    ).outerjoin(Vessel, Vessel.mmsi == AisPosition.mmsi)


async def fetch_snapshot_at(session: AsyncSession, at: datetime) -> list[dict]:
    """Latest position per vessel at or before the given time."""
    subq = (
        select(
            AisPosition.mmsi,
            func.max(AisPosition.t).label("max_t"),
        )
        .where(AisPosition.t <= at)
        .group_by(AisPosition.mmsi)
        .subquery()
    )
    stmt = (
        _position_select()
        .join(subq, (AisPosition.mmsi == subq.c.mmsi) & (AisPosition.t == subq.c.max_t))
        .order_by(AisPosition.mmsi)
    )
    rows = (await session.execute(stmt)).all()
    return [_row_to_event(row) for row in rows]


async def fetch_tracks_up_to(
    session: AsyncSession,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Per-vessel paths from start through end (inclusive), for trail rendering."""
    stmt = (
        _position_select()
        .where(AisPosition.t >= start, AisPosition.t <= end)
        .order_by(AisPosition.t, AisPosition.mmsi)
    )
    rows = (await session.execute(stmt)).all()
    by_mmsi: dict[int, list[list[float]]] = {}
    for row in rows:
        by_mmsi.setdefault(row.mmsi, []).append([float(row.lon), float(row.lat)])
    return [
        {"mmsi": mmsi, "path": path}
        for mmsi, path in by_mmsi.items()
        if len(path) >= 2
    ]


async def fetch_positions_between(
    session: AsyncSession,
    start: datetime,
    end: datetime,
) -> list[dict]:
    stmt = (
        _position_select()
        .where(AisPosition.t >= start, AisPosition.t < end)
        .order_by(AisPosition.t, AisPosition.mmsi)
    )
    rows = (await session.execute(stmt)).all()
    return [_row_to_event(row) for row in rows]
