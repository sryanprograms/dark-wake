"""Batch persistence of AISStream updates into PostGIS."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config.settings import Settings
from app.fusion.time_util import ensure_utc
from app.ingest.loader import connect, load_positions, upsert_vessels

logger = logging.getLogger(__name__)

OnFlushed = Callable[[dict[str, int]], Awaitable[None]]


def _position_record(update: dict[str, Any]) -> dict[str, Any]:
    t = update["t"]
    if isinstance(t, datetime):
        t = ensure_utc(t).isoformat()
    return {
        "mmsi": int(update["mmsi"]),
        "t": t,
        "lat": float(update["lat"]),
        "lon": float(update["lon"]),
        "sog": update.get("sog"),
        "cog": update.get("cog"),
        "heading": update.get("heading"),
        "name": update.get("name"),
        "ship_type": update.get("ship_type"),
        "flag": update.get("flag"),
        "callsign": update.get("callsign"),
        "imo": update.get("imo"),
    }


def _static_record(update: dict[str, Any]) -> dict[str, Any]:
    return {
        "mmsi": int(update["mmsi"]),
        "name": update.get("name"),
        "ship_type": update.get("ship_type"),
        "flag": update.get("flag"),
        "callsign": update.get("callsign"),
        "imo": update.get("imo"),
    }


def _flush_sync(
    database_url: str,
    positions: list[dict[str, Any]],
    static: list[dict[str, Any]],
) -> dict[str, int]:
    conn = connect(database_url)
    try:
        counts = {"vessels": 0, "positions": 0}
        if static:
            counts["vessels"] = upsert_vessels(conn, static)
        if positions:
            loaded = load_positions(conn, positions)
            counts["vessels"] = max(counts["vessels"], loaded["vessels"])
            counts["positions"] = loaded["positions"]
        return counts
    finally:
        conn.close()


class AisPersistBuffer:
    """Sample and batch AISStream updates before writing to PostGIS."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._enabled = settings.ais_persist_enabled and bool(settings.aisstream_api_key)
        self._min_interval = timedelta(seconds=settings.ais_persist_min_interval_s)
        self._pending_positions: list[dict[str, Any]] = []
        self._pending_static: dict[int, dict[str, Any]] = {}
        self._last_sampled: dict[int, datetime] = {}
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._on_flushed: list[OnFlushed] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    def on_flushed(self, handler: OnFlushed) -> None:
        self._on_flushed.append(handler)

    async def start(self) -> None:
        if not self._enabled:
            logger.info("AIS persistence disabled")
            return
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            "AIS persistence enabled (flush every %ss, min interval %ss per vessel)",
            self._settings.ais_persist_flush_interval_s,
            self._settings.ais_persist_min_interval_s,
        )

    async def stop(self) -> None:
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        await self.flush()

    async def offer(self, update: dict[str, Any]) -> None:
        if not self._enabled:
            return

        if update.get("kind") == "static":
            async with self._lock:
                self._pending_static[int(update["mmsi"])] = _static_record(update)
            return

        mmsi = int(update["mmsi"])
        reported_at = ensure_utc(update["t"])
        async with self._lock:
            last = self._last_sampled.get(mmsi)
            if last is not None and reported_at - last < self._min_interval:
                return
            self._last_sampled[mmsi] = reported_at
            self._pending_positions.append(_position_record(update))

    async def flush(self) -> dict[str, int]:
        async with self._lock:
            positions = self._pending_positions
            static = self._pending_static
            self._pending_positions = []
            self._pending_static = {}

        static_records = list(static.values())
        if not positions and not static_records:
            return {"vessels": 0, "positions": 0}

        try:
            counts = await asyncio.to_thread(
                _flush_sync,
                self._settings.database_url,
                positions,
                static_records,
            )
        except Exception:
            logger.exception("AIS persistence flush failed")
            # Restore the failed batch so it isn't lost, preserving any updates
            # that arrived while the write was in flight.
            async with self._lock:
                self._pending_positions = positions + self._pending_positions
                restored_static = dict(static)
                restored_static.update(self._pending_static)
                self._pending_static = restored_static
            return {"vessels": 0, "positions": 0}

        if counts["positions"] or counts["vessels"]:
            logger.debug(
                "Persisted AIS batch: %s positions, %s vessels",
                counts["positions"],
                counts["vessels"],
            )
            for handler in self._on_flushed:
                try:
                    await handler(counts)
                except Exception:
                    logger.exception("AIS persist on_flushed handler failed")
        return counts

    async def _flush_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._settings.ais_persist_flush_interval_s)
                await self.flush()
            except asyncio.CancelledError:
                raise
