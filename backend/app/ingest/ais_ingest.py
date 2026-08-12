"""Single shared AISStream consumer for live + historical persistence."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
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
        self.raw_messages = 0
        self.parsed_updates = 0
        self.skipped_messages = 0
        self.json_errors = 0
        self.last_error: str | None = None
        self.last_raw_at: datetime | None = None
        self.last_parsed_at: datetime | None = None
        self.last_message_type: str | None = None
        self._logged_first_raw = False
        self._logged_first_parsed = False

    @property
    def key_configured(self) -> bool:
        if self._settings is None:
            return False
        return bool((self._settings.aisstream_api_key or "").strip())

    @property
    def update_handler_count(self) -> int:
        return len(self._update_handlers)

    def diagnostics(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        last_raw_age = (
            round((now - self.last_raw_at).total_seconds(), 1)
            if self.last_raw_at is not None
            else None
        )
        last_parsed_age = (
            round((now - self.last_parsed_at).total_seconds(), 1)
            if self.last_parsed_at is not None
            else None
        )
        return {
            "ais_key_configured": self.key_configured,
            "ais_raw_messages": self.raw_messages,
            "ais_parsed_updates": self.parsed_updates,
            "ais_skipped_messages": self.skipped_messages,
            "ais_json_errors": self.json_errors,
            "ais_last_error": self.last_error,
            "ais_last_message_type": self.last_message_type,
            "ais_last_raw_age_s": last_raw_age,
            "ais_last_parsed_age_s": last_parsed_age,
            "ais_update_handlers": self.update_handler_count,
        }

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

        if not (settings.aisstream_api_key or "").strip():
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

    def _record_stats(self, stats: dict[str, Any]) -> None:
        self.raw_messages += int(stats.get("raw", 0))
        self.parsed_updates += int(stats.get("parsed", 0))
        self.skipped_messages += int(stats.get("skipped", 0))
        self.json_errors += int(stats.get("json_error", 0))
        if "error" in stats and stats["error"]:
            self.last_error = str(stats["error"])
        if stats.get("message_type"):
            self.last_message_type = str(stats["message_type"])
        if stats.get("last_raw_at") is not None:
            self.last_raw_at = stats["last_raw_at"]
            if not self._logged_first_raw:
                self._logged_first_raw = True
                logger.info(
                    "AISStream first raw message type=%s",
                    self.last_message_type,
                )
        if stats.get("last_parsed_at") is not None:
            self.last_parsed_at = stats["last_parsed_at"]
            if not self._logged_first_parsed:
                self._logged_first_parsed = True
                logger.info("AISStream first parsed update applied")

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

        await run_ais_stream(
            self._settings,
            on_connected=on_connected,
            on_update=on_update,
            on_stats=self._record_stats,
        )

    async def _notify_persist_flushed(self, _counts: dict[str, int]) -> None:
        for handler in self._flush_notify_handlers:
            try:
                await handler(True)
            except Exception:
                logger.exception("AIS ingest persist-flush notify failed")
