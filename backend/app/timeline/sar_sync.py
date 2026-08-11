"""Refresh GFW SAR detections into PostGIS for the unified timeline."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config.aoi import BBOX
from app.config.settings import Settings
from app.ingest.sar_gfw import fetch_detections
from app.ingest.sar_loader import connect, load_sar_detections, purge_sar_outside_bbox

logger = logging.getLogger(__name__)


def sync_recent_sar(settings: Settings, *, days: int | None = None) -> dict[str, int] | None:
    """Pull recent GFW SAR and upsert scenes without clearing existing rows."""
    if not settings.gfw_api_token:
        return None

    from app.config.thresholds import TIMELINE_HISTORY_DAYS

    lookback_days = days if days is not None else TIMELINE_HISTORY_DAYS
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)

    try:
        with httpx.Client() as client:
            detections = fetch_detections(
                BBOX,
                start,
                end,
                client,
                token=settings.gfw_api_token,
            )
    except Exception:
        logger.exception("GFW SAR fetch failed during timeline sync")
        return None

    if not detections:
        logger.info("No SAR detections returned for %s → %s", start.date(), end.date())
        return {"scenes": 0, "detections": 0}

    conn = connect(settings.database_url)
    try:
        purged = purge_sar_outside_bbox(conn, BBOX)
        if any(purged.values()):
            logger.info(
                "Purged SAR outside AOI: %s detections, %s scenes, %s contacts",
                purged["detections"],
                purged["scenes"],
                purged["contacts"],
            )
        counts = load_sar_detections(conn, detections, clear_existing=False)
    finally:
        conn.close()

    logger.info(
        "Timeline SAR sync: %s detections across %s scenes (%s → %s)",
        counts["detections"],
        counts["scenes"],
        start.date(),
        end.date(),
    )
    return counts
