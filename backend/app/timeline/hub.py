"""Unified timeline hub — live edge, historical seek, and SAR scene snap."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.config.aoi import AOI_NAME, BBOX
from app.config.settings import Settings, get_settings
from app.config.thresholds import REPLAY_SIM_SECONDS_PER_TICK, REPLAY_WINDOW_PRESETS
from app.db.session import get_session_factory
from app.live.detect import detect_ais_gap_resume, detect_ais_silent
from app.live.persist import persist_operator_event
from app.live.registry import VesselRegistry
from app.ingest.ais_ingest import get_ais_ingest_service
from app.replay.clock import parse_time
from app.replay.db_source import fetch_snapshot_at, fetch_tracks_up_to
from app.timeline.bounds import load_scenes, load_timeline_bounds
from app.timeline.sar_sync import sync_recent_sar
from app.timeline.scene_frame import build_scene_frame

logger = logging.getLogger(__name__)

Mode = Literal["live", "historical", "scene"]
BATCH_THRESHOLD = 25
GAP_SWEEP_INTERVAL_S = 60
BROADCAST_TRACK_INTERVAL_S = 30
GAP_SOURCE = "aisstream"
TRACK_WINDOW = REPLAY_WINDOW_PRESETS["24h"]

_hub: "TimelineHub | None" = None


def get_timeline_hub() -> "TimelineHub":
    global _hub
    if _hub is None:
        _hub = TimelineHub()
    return _hub


@dataclass
class TimelineClient:
    websocket: WebSocket
    mode: Mode = "live"
    playhead: datetime | None = None
    playing: bool = False
    speed: float = 1.0
    scene_id: int | None = None


class TimelineHub:
    def __init__(self) -> None:
        self.registry = VesselRegistry(track_max_age=timedelta(hours=6))
        self.clients: dict[WebSocket, TimelineClient] = {}
        self.ais_connected = False
        self._settings: Settings | None = None
        self._tasks: list[asyncio.Task] = []
        self._last_ingest_at: dict[int, datetime] = {}
        self._scenes: list[dict[str, Any]] = []
        self.data_start: datetime | None = None
        self.data_end: datetime | None = None
        self.position_count: int = 0

    def live_edge(self) -> datetime:
        return datetime.now(timezone.utc)

    async def start(self, settings: Settings | None = None) -> None:
        get_settings.cache_clear()
        self._settings = settings or get_settings()
        self.registry = VesselRegistry(
            track_max_age=timedelta(hours=self._settings.live_track_buffer_hours)
        )
        await self._refresh_bounds()

        ingest = get_ais_ingest_service()
        ingest.on_connected(self._on_ais_connected)
        ingest.on_update(self._handle_ais_update)
        ingest.on_persist_flushed(self._on_ais_persisted)

        self._tasks.append(asyncio.create_task(self._gap_sweep_loop()))
        self._tasks.append(asyncio.create_task(self._track_broadcast_loop()))
        if self._settings.gfw_api_token:
            self._tasks.append(asyncio.create_task(self._sar_sync_loop()))

    async def _on_ais_connected(self, connected: bool) -> None:
        self.ais_connected = connected
        await self._broadcast_timeline_state_to_live_clients()

    async def _on_ais_persisted(self, _connected: bool) -> None:
        await self._refresh_bounds()
        for client in list(self.clients.values()):
            try:
                await self._send_timeline_state(client)
            except Exception:
                await self._drop_client(client.websocket)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self.clients.clear()

    async def subscribe(self, websocket: WebSocket) -> TimelineClient:
        await self._refresh_bounds()
        self.ais_connected = get_ais_ingest_service().ais_connected
        client = TimelineClient(
            websocket=websocket,
            mode="live",
            playhead=self.live_edge(),
        )
        self.clients[websocket] = client
        await self._send_timeline_state(client)
        await self._send_live_snapshot(client)
        await self._send_state(client)
        return client

    async def unsubscribe(self, websocket: WebSocket) -> None:
        self.clients.pop(websocket, None)

    async def handle_action(self, client: TimelineClient, msg: dict[str, Any]) -> None:
        action = msg.get("action")
        if action == "go_live":
            await self._go_live(client)
        elif action == "seek":
            t = msg.get("t")
            if t is not None:
                await self._seek(client, t)
        elif action == "snap_scene":
            raw_id = msg.get("scene_id")
            if raw_id is not None:
                await self._snap_scene(client, int(raw_id))
        elif action == "play":
            client.playing = True
            await self._send_state(client)
        elif action == "pause":
            client.playing = False
            await self._send_state(client)
        elif action == "speed":
            client.speed = max(0.1, float(msg.get("multiplier", 1.0)))
        elif action == "ping":
            await self._send_json(client.websocket, {"type": "pong"})

    async def tick_client(self, client: TimelineClient) -> None:
        if not client.playing or client.mode != "historical":
            return
        if client.playhead is None or self.data_start is None or self.data_end is None:
            return

        window_tick_start = client.playhead
        window_tick_end = min(
            self.data_end,
            window_tick_start + timedelta(seconds=REPLAY_SIM_SECONDS_PER_TICK * client.speed),
        )
        await self._send_historical_frame(client, at=window_tick_end)
        client.playhead = window_tick_end
        if client.playhead >= self.data_end:
            client.playing = False
        await self._send_state(client)

    async def _refresh_bounds(self) -> None:
        factory = get_session_factory()
        async with factory() as session:
            self.data_start, self.data_end, self.position_count, _scene_count = (
                await load_timeline_bounds(session)
            )
            self._scenes = await load_scenes(session)

    async def _go_live(self, client: TimelineClient) -> None:
        client.mode = "live"
        client.playing = False
        client.scene_id = None
        client.playhead = self.live_edge()
        await self._send_timeline_state(client)
        await self._send_live_snapshot(client)
        await self._send_state(client)

    async def _seek(self, client: TimelineClient, t: str | datetime) -> None:
        target = parse_time(t)
        live = self.live_edge()
        if target >= live - timedelta(seconds=30):
            await self._go_live(client)
            return

        data_start = self.data_start or target
        data_end = self.data_end or target
        client.mode = "historical"
        client.playing = False
        client.scene_id = None
        client.playhead = max(data_start, min(data_end, target))
        await self._send_timeline_state(client)
        await self._send_historical_frame(client, at=client.playhead)
        await self._send_state(client)

    async def _snap_scene(self, client: TimelineClient, scene_id: int) -> None:
        factory = get_session_factory()
        async with factory() as session:
            frame = await build_scene_frame(session, scene_id)
            scene_t = frame.get("t")
            if scene_t is None:
                logger.warning("snap_scene: scene_id=%s has no scene time", scene_id)
                return
            playhead = parse_time(scene_t)
            data_start = self.data_start
            window_start = (
                max(data_start, playhead - TRACK_WINDOW) if data_start else playhead - TRACK_WINDOW
            )
            tracks = await fetch_tracks_up_to(session, window_start, playhead)
        client.mode = "scene"
        client.playing = False
        client.scene_id = scene_id
        client.playhead = playhead
        frame["tracks"] = tracks
        await self._send_timeline_state(client)
        await self._send_json(client.websocket, frame)
        await self._send_state(client)

    async def _send_timeline_state(self, client: TimelineClient) -> None:
        data_start = self.data_start
        data_end = self.data_end
        playhead = client.playhead or self.live_edge()
        await self._send_json(
            client.websocket,
            {
                "type": "timeline_state",
                "data_start": data_start.astimezone(timezone.utc).isoformat()
                if data_start
                else None,
                "data_end": data_end.astimezone(timezone.utc).isoformat() if data_end else None,
                "live_edge": self.live_edge().isoformat(),
                "playhead": playhead.astimezone(timezone.utc).isoformat(),
                "current": playhead.astimezone(timezone.utc).isoformat(),
                "mode": client.mode,
                "playing": client.playing,
                "speed": client.speed,
                "current_scene_id": str(client.scene_id) if client.scene_id is not None else None,
                "scenes": self._scenes,
                "position_count": self.position_count,
                "ais_connected": self.ais_connected,
                "id": AOI_NAME,
                "name": AOI_NAME,
                "bbox": BBOX,
            },
        )

    async def _send_state(self, client: TimelineClient) -> None:
        playhead = client.playhead or self.live_edge()
        await self._send_json(
            client.websocket,
            {
                "type": "state",
                "current": playhead.astimezone(timezone.utc).isoformat(),
                "playing": client.playing,
                "mode": client.mode,
                "current_scene_id": str(client.scene_id) if client.scene_id is not None else None,
            },
        )

    async def _send_live_snapshot(self, client: TimelineClient) -> None:
        snapshot = self.registry.snapshot()
        tracks = self.registry.tracks()
        from_db = False
        if not snapshot:
            playhead = self.live_edge()
            data_start = self.data_start
            if data_start is not None:
                try:
                    window_start = max(data_start, playhead - TRACK_WINDOW)
                    factory = get_session_factory()
                    async with factory() as session:
                        snapshot = await fetch_snapshot_at(session, playhead)
                        tracks = await fetch_tracks_up_to(session, window_start, playhead)
                    from_db = bool(snapshot)
                except Exception:
                    logger.debug("Live snapshot DB fallback failed", exc_info=True)
        if snapshot:
            if from_db:
                vessels = [{k: v for k, v in e.items() if k != "type"} for e in snapshot]
                await self._send_json(
                    client.websocket,
                    {"type": "ais_batch", "vessels": vessels, "source": "db_snapshot"},
                )
            else:
                await self._send_ais_events(client.websocket, snapshot)
        if tracks:
            await self._send_json(client.websocket, {"type": "tracks_batch", "tracks": tracks})

    async def _send_historical_frame(self, client: TimelineClient, *, at: datetime) -> None:
        data_start = self.data_start
        if data_start is None:
            return
        window_start = max(data_start, at - TRACK_WINDOW)
        factory = get_session_factory()
        async with factory() as session:
            snapshot = await fetch_snapshot_at(session, at)
            tracks = await fetch_tracks_up_to(session, window_start, at)
        await self._send_ais_events(client.websocket, snapshot)
        await self._send_json(client.websocket, {"type": "tracks_batch", "tracks": tracks})

    async def _handle_ais_update(self, update: dict[str, Any]) -> None:
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

        event = self.registry.vessel_ais_event(state)
        await self._broadcast_ais_to_live_clients([event])

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
                    await self._broadcast_to_live_clients(
                        {"type": "tracks_batch", "tracks": tracks}
                    )
            except asyncio.CancelledError:
                raise

    async def _sar_sync_loop(self) -> None:
        assert self._settings is not None
        while True:
            try:
                counts = await asyncio.to_thread(sync_recent_sar, self._settings)
                if counts and counts.get("scenes", 0) > 0:
                    await self._refresh_bounds()
                    for client in list(self.clients.values()):
                        try:
                            await self._send_timeline_state(client)
                        except Exception:
                            await self._drop_client(client.websocket)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Timeline SAR sync failed")
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
        await self._broadcast_to_live_clients(payload)

    def _live_clients(self) -> list[TimelineClient]:
        return [c for c in self.clients.values() if c.mode == "live"]

    async def _broadcast_timeline_state_to_live_clients(self) -> None:
        for client in self._live_clients():
            try:
                await self._send_timeline_state(client)
            except Exception:
                await self._drop_client(client.websocket)

    async def _broadcast_ais_to_live_clients(self, events: list[dict[str, Any]]) -> None:
        for client in self._live_clients():
            try:
                await self._send_ais_events(client.websocket, events)
            except Exception:
                await self._drop_client(client.websocket)

    async def _broadcast_to_live_clients(self, message: dict[str, Any]) -> None:
        for client in self._live_clients():
            try:
                await self._send_json(client.websocket, message)
            except Exception:
                await self._drop_client(client.websocket)

    async def _drop_client(self, websocket: WebSocket) -> None:
        self.clients.pop(websocket, None)

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
