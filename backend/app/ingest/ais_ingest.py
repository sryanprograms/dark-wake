"""Single shared AISStream consumer for live + historical persistence."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.config.settings import Settings
from app.ingest.ais_persist import AisPersistBuffer
from app.timeline.ais_consumer import run_ais_stream

logger = logging.getLogger(__name__)

OnConnected = Callable[[bool], Awaitable[None]]
OnUpdate = Callable[[dict[str, Any]], Awaitable[None]]

_service: "AisIngestService | None" = None


def get_ais_ingest_service() -> "AisIngestService":
    global _service
    if _service is None:
        _service = AisIngestService()
    return _service


class AisIngestService:
    """One AISStream WebSocket fanning out to hubs and PostGIS persistence."""

    def __init__(self) -> None:
        self.ais_connected = False
        self._settings: Settings | None = None
        self._persist: AisPersistBuffer | None = None
        self._connected_handlers: list[OnConnected] = []
        self._update_handlers: list[OnUpdate] = []
        self._task: asyncio.Task | None = None
        self._flush_notify_handlers: list[OnConnected] = []

    def on_connected(self, handler: OnConnected) -> None:
        self._connected_handlers.append(handler)

    def on_update(self, handler: OnUpdate) -> None:
        self._update_handlers.append(handler)

    def on_persist_flushed(self, handler: OnConnected) -> None:
        """Register async callback after a DB flush (e.g. refresh timeline bounds)."""
        self._flush_notify_handlers.append(handler)

    async def start(self, settings: Settings) -> None:
        if self._task is not None:
            return

        self._settings = settings
        self._persist = AisPersistBuffer(settings)
        self._persist.on_flushed(self._notify_persist_flushed)
        await self._persist.start()

        if not settings.aisstream_api_key:
            logger.warning("AISSTREAM_API_KEY not set — AIS ingest disabled")
            return

        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._persist is not None:
            await self._persist.stop()
            self._persist = None

        self.ais_connected = False

    async def _run(self) -> None:
        assert self._settings is not None
        assert self._persist is not None

        async def on_connected(connected: bool) -> None:
            self.ais_connected = connected
            for handler in self._connected_handlers:
                try:
                    await handler(connected)
                except Exception:
                    logger.exception("AIS ingest on_connected handler failed")

        async def on_update(update: dict[str, Any]) -> None:
            await self._persist.offer(update)
            for handler in self._update_handlers:
                try:
                    await handler(update)
                except Exception:
                    logger.exception("AIS ingest on_update handler failed")

        await run_ais_stream(self._settings, on_connected=on_connected, on_update=on_update)

    async def _notify_persist_flushed(self, _counts: dict[str, int]) -> None:
        for handler in self._flush_notify_handlers:
            try:
                await handler(True)
            except Exception:
                logger.exception("AIS ingest persist-flush notify failed")
