"""DarkWake FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.rest import router as rest_router
from app.api.ws import handle_replay_ws

app = FastAPI(title="DarkWake", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rest_router)
app.websocket("/ws/replay")(handle_replay_ws)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
