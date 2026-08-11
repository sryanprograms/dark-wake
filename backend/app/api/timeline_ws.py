"""WebSocket handler for unified /ws/timeline."""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect

from app.timeline.hub import get_timeline_hub

TICK_INTERVAL_S = 0.5


async def handle_timeline_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    hub = get_timeline_hub()
    client = await hub.subscribe(websocket)

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=TICK_INTERVAL_S)
                msg = json.loads(raw)
                await hub.handle_action(client, msg)
            except asyncio.TimeoutError:
                await hub.tick_client(client)
            except json.JSONDecodeError:
                continue
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(websocket)
