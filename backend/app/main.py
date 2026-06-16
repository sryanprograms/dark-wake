"""DarkWake FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.live_ws import handle_live_ws
from app.api.rest import router as rest_router
from app.api.ws import handle_replay_ws
from app.config.settings import get_settings
from app.live.hub import get_live_hub


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings.cache_clear()
    hub = get_live_hub()
    await hub.start(get_settings())
    yield
    await hub.stop()


app = FastAPI(title="DarkWake", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rest_router)
app.websocket("/ws/replay")(handle_replay_ws)
app.websocket("/ws/live")(handle_live_ws)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
