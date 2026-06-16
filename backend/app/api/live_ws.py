"""WebSocket live handler."""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect

from app.live.hub import get_live_hub


async def handle_live_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    hub = get_live_hub()
    await hub.subscribe(websocket)

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(raw)
                if msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(websocket)
