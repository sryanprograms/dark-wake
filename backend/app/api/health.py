"""Liveness, readiness, and status endpoints for deployment monitoring."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.db.session import get_engine
from app.ingest.ais_ingest import get_ais_ingest_service
from app.live.hub import get_live_hub

router = APIRouter(tags=["monitoring"])

_STARTED_AT = time.monotonic()

APP_VERSION = "0.2.0"


async def _db_ok() -> bool:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/health")
def health() -> dict[str, str]:
    """Cheap liveness probe — used by the platform health check."""
    return {"status": "ok", "version": APP_VERSION}


@router.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    """Readiness probe — 503 until the database is reachable."""
    db_ok = await _db_ok()
    if not db_ok:
        response.status_code = 503
    return {"status": "ok" if db_ok else "unavailable", "db": db_ok}


@router.get("/status")
async def status(response: Response) -> dict[str, object]:
    """Detailed status for dashboards and external uptime monitors."""
    db_ok = await _db_ok()
    hub = get_live_hub()
    ingest = get_ais_ingest_service()

    healthy = db_ok
    if not healthy:
        response.status_code = 503

    return {
        "status": "ok" if healthy else "degraded",
        "version": APP_VERSION,
        "uptime_seconds": round(time.monotonic() - _STARTED_AT, 1),
        "time": datetime.now(timezone.utc).isoformat(),
        "db": db_ok,
        "ais_connected": ingest.ais_connected,
        "vessel_count": len(hub.registry),
        "sar_detection_count": len(hub._sar_cache),
        "ws_client_count": len(hub.clients),
    }
