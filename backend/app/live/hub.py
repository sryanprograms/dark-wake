"""Live AIS hub — AISStream consumer and client fan-out."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from datetime import datetime, timedelta, timezone
from typing import Any

import certifi
import websockets
from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.config.aoi import AOI_NAME, BBOX
from app.config.settings import Settings, get_settings
from app.db.session import get_session_factory
from app.ingest.ais_stream import AISSTREAM_URL, build_subscription_message, parse_aisstream_message
from app.live.detect import detect_ais_gap_resume, detect_ais_silent
from app.live.persist import persist_operator_event
from app.live.registry import VesselRegistry
from app.live.sar_poller import poll_sar_detections

logger = logging.getLogger(__name__)

BATCH_THRESHOLD = 25
GAP_SWEEP_INTERVAL_S = 60
BROADCAST_TRACK_INTERVAL_S = 30
GAP_SOURCE = "aisstream"

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
        self._last_ingest_at: dict[int, datetime] = {}

    async def start(self, settings: Settings | None = None) -> None:
        get_settings.cache_clear()
        self._settings = settings or get_settings()
        self.registry = VesselRegistry(
            track_max_age=timedelta(hours=self._settings.live_track_buffer_hours)
        )
        if self._settings.aisstream_api_key:
            self._tasks.append(asyncio.create_task(self._run_ais_stream()))
        else:
            logger.warning("AISSTREAM_API_KEY not set — live AIS ingest disabled")
        self._tasks.append(asyncio.create_task(self._gap_sweep_loop()))
        self._tasks.append(asyncio.create_task(self._track_broadcast_loop()))
        if self._settings.gfw_api_token:
            self._tasks.append(asyncio.create_task(self._sar_poll_loop()))

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

    async def unsubscribe(self, websocket: WebSocket) -> None:
        self.clients.discard(websocket)

    async def _run_ais_stream(self) -> None:
        assert self._settings is not None
        api_key = self._settings.aisstream_api_key
        subscription = build_subscription_message(api_key)
        ssl_context = ssl.create_default_context(cafile=certifi.where())

        while True:
            try:
                async with websockets.connect(AISSTREAM_URL, ssl=ssl_context) as ws:
                    await ws.send(json.dumps(subscription))
                    self.ais_connected = True
                    await self._broadcast_live_state()
                    logger.info("AISStream connected for AOI %s", AOI_NAME)

                    async for raw in ws:
                        try:
                            message = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if "error" in message:
                            logger.error("AISStream error: %s", message.get("error"))
                            break
                        update = parse_aisstream_message(message)
                        if update is None:
                            continue
                        await self._handle_update(update)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AISStream connection failed; retrying in 10s")
                self.ais_connected = False
                await self._broadcast_live_state()
                await asyncio.sleep(10)

    async def _handle_update(self, update: dict[str, Any]) -> None:
        if update["kind"] == "static":
            self.registry.apply_static(update)
            return

        mmsi = int(update["mmsi"])
        ingest_at = datetime.now(timezone.utc)
        previous_at = self._last_ingest_at.get(mmsi)

        state = self.registry.apply_position(
            update,
            ingest_at=ingest_at,
            gap_monitor=True,
        )
        self._last_ingest_at[mmsi] = ingest_at

        await self._send_ais_events_to_all([self.registry.vessel_ais_event(state)])

        alert = detect_ais_gap_resume(
            state,
            previous_at=previous_at,
            current_at=ingest_at,
            source=GAP_SOURCE,
        )
        if alert:
            await self._emit_alert(alert, mmsi=mmsi)

    async def _gap_sweep_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(GAP_SWEEP_INTERVAL_S)
                now = datetime.now(timezone.utc)
                for state in self.registry.vessels():
                    alert = detect_ais_silent(state, now=now, source=GAP_SOURCE)
                    if alert:
                        await self._emit_alert(alert, mmsi=state.mmsi)
            except asyncio.CancelledError:
                raise

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
                    await self._broadcast({"type": "sar_batch", "detections": new_dets})
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("SAR poll failed")
            await asyncio.sleep(self._settings.sar_poll_interval_s)

    async def _emit_alert(self, alert: dict[str, Any], *, mmsi: int) -> None:
        excerpt = self.registry.track_excerpt(mmsi)
        try:
            factory = get_session_factory()
            async with factory() as session:
                event_id = await persist_operator_event(
                    session, event=alert, track_excerpt=excerpt
                )
        except Exception:
            logger.exception("Failed to persist operator event")
            event_id = None

        payload = {"type": "alert", **alert, "id": event_id}
        await self._broadcast(payload)

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
