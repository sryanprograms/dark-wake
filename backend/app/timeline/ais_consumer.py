"""Shared AISStream consumer loop for live ingest."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from collections.abc import Awaitable, Callable
from typing import Any

import certifi
import websockets

from app.config.aoi import AOI_NAME
from app.config.settings import Settings
from app.ingest.ais_stream import AISSTREAM_URL, build_subscription_message, parse_aisstream_message

logger = logging.getLogger(__name__)

OnConnected = Callable[[bool], Awaitable[None]]
OnUpdate = Callable[[dict[str, Any]], Awaitable[None]]


async def run_ais_stream(
    settings: Settings,
    *,
    on_connected: OnConnected,
    on_update: OnUpdate,
) -> None:
    """Connect to AISStream and invoke callbacks for each position/static update."""
    api_key = settings.aisstream_api_key
    if not api_key:
        logger.warning("AISSTREAM_API_KEY not set — live AIS ingest disabled")
        return

    subscription = build_subscription_message(api_key)
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    while True:
        try:
            async with websockets.connect(AISSTREAM_URL, ssl=ssl_context) as ws:
                await ws.send(json.dumps(subscription))
                await on_connected(True)
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
                    await on_update(update)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("AISStream connection failed; retrying in 10s")
            await on_connected(False)
            await asyncio.sleep(10)
