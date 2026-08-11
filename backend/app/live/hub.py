"""Live AIS hub — AISStream consumer and client fan-out."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.config.aoi import AOI_NAME, BBOX
from app.config.settings import Settings, get_settings
from app.ingest.ais_ingest import get_ais_ingest_service
from app.live.registry import VesselRegistry
from app.live.sar_poller import poll_sar_detections

logger = logging.getLogger(__name__)

BATCH_THRESHOLD = 25
BROADCAST_TRACK_INTERVAL_S = 30

_hub: "LiveHub | None" = None


def get_live_hub() -> "LiveHub":
    global _hub
    if _hub is None:
        _hub = LiveHub()
    return _hub


class LiveHub:
    def __init__(self) -> None:
        self.registry = VesselRegistry(track_max_age=timedelta(hours=6))
        self.clients: set[WebSocket] = set()
        self.ais_connected = False
        self._settings: Settings | None = None
        self._tasks: list[asyncio.Task] = []
        self._sar_seen: set[str] = set()
        self._sar_cache: list[dict[str, Any]] = []

    async def start(self, settings: Settings | None = None) -> None:
        get_settings.cache_clear()
        self._settings = settings or get_settings()
        self.registry = VesselRegistry(
            track_max_age=timedelta(hours=self._settings.live_track_buffer_hours)
        )

        ingest = get_ais_ingest_service()
        ingest.on_connected(self._on_ais_connected)
        ingest.on_update(self._handle_update)

        # Gap detection / alert persistence is owned solely by TimelineHub to
        # avoid duplicate alerts on the shared AIS ingest service.
        self._tasks.append(asyncio.create_task(self._track_broadcast_loop()))
        if self._settings.gfw_api_token:
            self._tasks.append(asyncio.create_task(self._sar_poll_loop()))

    async def _on_ais_connected(self, connected: bool) -> None:
        self.ais_connected = connected
        await self._broadcast_live_state()

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self.clients.clear()

    async def subscribe(self, websocket: WebSocket) -> None:
        self.clients.add(websocket)
        await self._send_json(
            websocket,
            {
                "type": "live_state",
                "mode": "live",
                "id": AOI_NAME,
                "name": AOI_NAME,
                "bbox": BBOX,
                "vessel_count": len(self.registry),
                "ais_connected": self.ais_connected,
                "current": datetime.now(timezone.utc).isoformat(),
            },
        )
        snapshot = self.registry.snapshot()
        if snapshot:
            await self._send_ais_events(websocket, snapshot)
        tracks = self.registry.tracks()
        if tracks:
            await self._send_json(websocket, {"type": "tracks_batch", "tracks": tracks})
        if self._sar_cache:
            await self._send_json(
                websocket,
                {"type": "sar_batch", "detections": self._sar_cache},
            )

    async def unsubscribe(self, websocket: WebSocket) -> None:
        self.clients.discard(websocket)

    async def _handle_update(self, update: dict[str, Any]) -> None:
        if update["kind"] == "static":
            self.registry.apply_static(update)
            return

        state = self.registry.apply_position(
            update,
            ingest_at=datetime.now(timezone.utc),
        )

        await self._send_ais_events_to_all([self.registry.vessel_ais_event(state)])

    async def _track_broadcast_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(BROADCAST_TRACK_INTERVAL_S)
                tracks = self.registry.tracks()
                if tracks:
                    await self._broadcast({"type": "tracks_batch", "tracks": tracks})
            except asyncio.CancelledError:
                raise

    async def _sar_poll_loop(self) -> None:
        assert self._settings is not None
        while True:
            try:
                new_dets, self._sar_seen = await poll_sar_detections(
                    self._settings,
                    seen=self._sar_seen,
                )
                if new_dets:
                    by_id = {d["id"]: d for d in self._sar_cache}
                    for det in new_dets:
                        by_id[det["id"]] = det
                    self._sar_cache = list(by_id.values())
                    await self._broadcast(
                        {"type": "sar_batch", "detections": self._sar_cache}
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("SAR poll failed")
            await asyncio.sleep(self._settings.sar_poll_interval_s)

    async def _broadcast_live_state(self) -> None:
        await self._broadcast(
            {
                "type": "live_state",
                "mode": "live",
                "id": AOI_NAME,
                "name": AOI_NAME,
                "bbox": BBOX,
                "vessel_count": len(self.registry),
                "ais_connected": self.ais_connected,
                "current": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def _broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for client in list(self.clients):
            try:
                await self._send_json(client, message)
            except Exception:
                dead.append(client)
        for client in dead:
            self.clients.discard(client)

    async def _send_ais_events_to_all(self, events: list[dict[str, Any]]) -> None:
        dead: list[WebSocket] = []
        for client in list(self.clients):
            try:
                await self._send_ais_events(client, events)
            except Exception:
                dead.append(client)
        for client in dead:
            self.clients.discard(client)

    async def _send_ais_events(self, websocket: WebSocket, events: list[dict]) -> None:
        if len(events) > BATCH_THRESHOLD:
            vessels = [{k: v for k, v in e.items() if k != "type"} for e in events]
            await self._send_json(websocket, {"type": "ais_batch", "vessels": vessels})
            return
        for event in events:
            await self._send_json(websocket, event)

    async def _send_json(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        if websocket.client_state != WebSocketState.CONNECTED:
            return
        await websocket.send_json(message)
