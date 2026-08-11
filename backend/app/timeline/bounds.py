"""Timeline extent and SAR scene markers from PostGIS."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.aoi import DEFAULT_END, DEFAULT_START
from app.config.thresholds import TIMELINE_HISTORY_DAYS
from app.db.models import AisPosition, Contact, SarScene
from app.replay.clock import parse_time

logger = logging.getLogger(__name__)


def timeline_window(
    now: datetime | None = None,
    *,
    history_days: int = TIMELINE_HISTORY_DAYS,
) -> tuple[datetime, datetime]:
    """Return (window_start, window_end) for the allowed scrubber range."""
    window_end = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    window_start = window_end - timedelta(days=history_days)
    return window_start, window_end


def clamp_timeline_extent(
    t_min: datetime | None,
    t_max: datetime | None,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Intersect stored data extent with the rolling timeline window."""
    window_start, window_end = timeline_window(now)
    if t_min is None or t_max is None:
        return window_start, window_end

    t_min = t_min.astimezone(timezone.utc)
    t_max = t_max.astimezone(timezone.utc)
    data_start = max(t_min, window_start)
    data_end = min(t_max, window_end)
    if data_start > data_end:
        return window_start, window_end
    return data_start, data_end


async def load_ais_bounds(session: AsyncSession) -> tuple:
    """Return (data_start, data_end, position_count)."""
    row = (
        await session.execute(select(func.min(AisPosition.t), func.max(AisPosition.t), func.count()))
    ).one()
    t_min, t_max, count = row[0], row[1], row[2]
    if t_min is None or t_max is None or count == 0:
        return parse_time(DEFAULT_START), parse_time(DEFAULT_END), 0
    return t_min, t_max, count


async def load_timeline_bounds(session: AsyncSession) -> tuple:
    """Return (data_start, data_end, ais_count, scene_count).

    Timeline extent spans both AIS positions and SAR scenes, clamped to the
    last TIMELINE_HISTORY_DAYS ending at now.
    """
    window_start, window_end = timeline_window()

    ais_row = (
        await session.execute(
            select(func.min(AisPosition.t), func.max(AisPosition.t), func.count(AisPosition.id))
        )
    ).one()
    ais_min, ais_max, ais_count = ais_row[0], ais_row[1], ais_row[2] or 0

    ais_in_window = (
        await session.execute(
            select(func.count(AisPosition.id)).where(
                AisPosition.t >= window_start,
                AisPosition.t <= window_end,
            )
        )
    ).scalar_one()

    sar_min: datetime | None = None
    sar_max: datetime | None = None
    scene_count = 0
    try:
        sar_row = (
            await session.execute(
                select(func.min(SarScene.t), func.max(SarScene.t), func.count(SarScene.id))
            )
        ).one()
        sar_min, sar_max, _scene_total = sar_row[0], sar_row[1], sar_row[2] or 0
        scene_count = (
            await session.execute(
                select(func.count(SarScene.id)).where(
                    SarScene.t >= window_start,
                    SarScene.t <= window_end,
                )
            )
        ).scalar_one()
    except Exception:
        logger.debug("sar_scene table unavailable; SAR bounds omitted")

    starts = [t for t in (ais_min, sar_min) if t is not None]
    ends = [t for t in (ais_max, sar_max) if t is not None]
    if not starts:
        return window_start, window_end, ais_in_window, scene_count

    data_start, data_end = clamp_timeline_extent(min(starts), max(ends))
    return data_start, data_end, ais_in_window, scene_count


async def load_scenes(session: AsyncSession) -> list[dict]:
    """SAR scene markers for the timeline rail (within the rolling window)."""
    window_start, window_end = timeline_window()
    try:
        rows = (
            await session.execute(
                select(SarScene)
                .where(SarScene.t >= window_start, SarScene.t <= window_end)
                .order_by(SarScene.t)
            )
        ).scalars().all()
    except Exception:
        logger.debug("sar_scene table unavailable; returning empty scene list")
        return []

    dark_counts: dict[int, int] = {}
    if rows:
        try:
            dark_rows = (
                await session.execute(
                    select(Contact.scene_id, func.count())
                    .where(Contact.classification == "dark")
                    .group_by(Contact.scene_id)
                )
            ).all()
            dark_counts = {int(sid): int(cnt) for sid, cnt in dark_rows if sid is not None}
        except Exception:
            logger.debug("contact table unavailable; dark_count defaults to 0")

    return [
        {
            "id": row.id,
            "t": row.t.astimezone(timezone.utc).isoformat(),
            "scene_id": row.scene_id,
            "detection_count": row.detection_count,
            "dark_count": dark_counts.get(row.id, 0),
        }
        for row in rows
    ]
