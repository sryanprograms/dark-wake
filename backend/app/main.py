"""DarkWake FastAPI application."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

from app.api.health import router as health_router
from app.api.live_ws import handle_live_ws
from app.api.rest import router as rest_router
from app.api.timeline import router as timeline_router
from app.api.timeline_ws import handle_timeline_ws
from app.api.ws import handle_replay_ws
from app.config.settings import get_settings
from app.ingest.ais_ingest import get_ais_ingest_service
from app.live.hub import get_live_hub
from app.timeline.hub import get_timeline_hub

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

_DEFAULT_CORS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:5174,http://127.0.0.1:5174"
)


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", _DEFAULT_CORS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings.cache_clear()
    settings = get_settings()
    # Register hub handlers before starting AIS ingest so the first messages
    # are not dropped during the startup race.
    timeline_hub = get_timeline_hub()
    await timeline_hub.start(settings)
    live_hub = get_live_hub()
    await live_hub.start(settings)
    ingest = get_ais_ingest_service()
    await ingest.start(settings)
    yield
    await timeline_hub.stop()
    await live_hub.stop()
    await ingest.stop()


app = FastAPI(title="DarkWake", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(rest_router)
app.include_router(timeline_router)
app.websocket("/ws/timeline")(handle_timeline_ws)
app.websocket("/ws/replay")(handle_replay_ws)
app.websocket("/ws/live")(handle_live_ws)


# Serve the built frontend (production single-origin deploy). No-op in local dev
# where the SPA is served by Vite and this directory does not exist.
_STATIC_DIR = Path(os.getenv("FRONTEND_DIST", Path(__file__).parent / "static")).resolve()

if _STATIC_DIR.is_dir():
    _assets_dir = _STATIC_DIR / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str, request: Request) -> Response:
        candidate = (_STATIC_DIR / full_path).resolve()
        if full_path and _STATIC_DIR in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_STATIC_DIR / "index.html")
