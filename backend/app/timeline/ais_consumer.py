"""Shared AISStream consumer loop for live ingest."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

import certifi
import websockets
from websockets.exceptions import InvalidStatus

from app.config.aoi import AOI_NAME
from app.config.settings import Settings
from app.ingest.ais_stream import AISSTREAM_URL, build_subscription_message, parse_aisstream_message

logger = logging.getLogger(__name__)

OnConnected = Callable[[bool], Awaitable[None]]
OnUpdate = Callable[[dict[str, Any]], Awaitable[None]]
OnStats = Callable[[dict[str, Any]], None]

_MIN_BACKOFF_S = 10
_MAX_BACKOFF_S = 600
_RATE_LIMIT_BACKOFF_S = 120


def _retry_delay(exc: BaseException, attempt: int) -> int:
    """Backoff for reconnects; 429s wait longer so we don't deepen the ban."""
    if isinstance(exc, InvalidStatus) and getattr(exc, "response", None) is not None:
        if exc.response.status_code == 429:
            return min(_RATE_LIMIT_BACKOFF_S * max(1, attempt), _MAX_BACKOFF_S)
    text = str(exc)
    if "429" in text:
        return min(_RATE_LIMIT_BACKOFF_S * max(1, attempt), _MAX_BACKOFF_S)
    return min(_MIN_BACKOFF_S * (2 ** max(0, attempt - 1)), _MAX_BACKOFF_S)


async def run_ais_stream(
    settings: Settings,
    *,
    on_connected: OnConnected,
    on_update: OnUpdate,
    on_stats: OnStats | None = None,
) -> None:
    """Connect to AISStream and invoke callbacks for each position/static update."""
    api_key = (settings.aisstream_api_key or "").strip()
    if not api_key:
        logger.warning("AISSTREAM_API_KEY not set — live AIS ingest disabled")
        return

    subscription = build_subscription_message(api_key)
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    attempt = 0

    while True:
        try:
            async with websockets.connect(AISSTREAM_URL, ssl=ssl_context) as ws:
                await ws.send(json.dumps(subscription))
                await on_connected(True)
                attempt = 0
                logger.info(
                    "AISStream connected for AOI %s (key_len=%s)",
                    AOI_NAME,
                    len(api_key),
                )

                async for raw in ws:
                    try:
                        message = json.loads(raw)
                    except json.JSONDecodeError:
                        if on_stats is not None:
                            on_stats({"raw": 1, "json_error": 1})
                        continue

                    if "error" in message:
                        err = str(message.get("error"))
                        logger.error("AISStream error: %s", err)
                        if on_stats is not None:
                            on_stats({"raw": 1, "error": err})
                        break

                    message_type = message.get("MessageType")
                    update = parse_aisstream_message(message)
                    if update is None:
                        if on_stats is not None:
                            on_stats(
                                {
                                    "raw": 1,
                                    "skipped": 1,
                                    "message_type": message_type,
                                    "last_raw_at": datetime.now(timezone.utc),
                                }
                            )
                        continue

                    if on_stats is not None:
                        on_stats(
                            {
                                "raw": 1,
                                "parsed": 1,
                                "message_type": message_type,
                                "last_raw_at": datetime.now(timezone.utc),
                                "last_parsed_at": datetime.now(timezone.utc),
                            }
                        )
                    await on_update(update)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            attempt += 1
            delay = _retry_delay(exc, attempt)
            logger.exception(
                "AISStream connection failed; retrying in %ss (attempt %s)",
                delay,
                attempt,
            )
            if on_stats is not None:
                on_stats({"error": f"{type(exc).__name__}: {exc}"})
            await on_connected(False)
            await asyncio.sleep(delay)
