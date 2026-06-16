"""WebSocket replay handler."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta, timezone

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from app.config.aoi import AOI_NAME, BBOX, DEFAULT_END, DEFAULT_START
from app.config.thresholds import REPLAY_DEFAULT_WINDOW_PRESET, REPLAY_SIM_SECONDS_PER_TICK
from app.db.models import AisPosition
from app.db.session import get_session_factory
from app.replay.clock import parse_time
from app.replay.db_source import fetch_snapshot_at, fetch_tracks_up_to
from app.replay.window import compute_window, normalize_preset

BATCH_THRESHOLD = 25


async def _send_ais_events(websocket, events: list[dict]) -> None:
    if len(events) > BATCH_THRESHOLD:
        await websocket.send_json({"type": "ais_batch", "vessels": events})
        return
    for event in events:
        await websocket.send_json(event)


async def _send_frame(websocket, session, *, at, window_start) -> None:
    """Snapshot at `at` plus movement trails from window start."""
    snapshot = await fetch_snapshot_at(session, at)
    tracks = await fetch_tracks_up_to(session, window_start, at)
    await _send_ais_events(websocket, snapshot)
    await websocket.send_json({"type": "tracks_batch", "tracks": tracks})


def _scenario_payload(
    *,
    data_start,
    data_end,
    window_start,
    window_end,
    window_preset: str,
    count: int,
    current,
) -> dict:
    return {
        "type": "scenario",
        "id": AOI_NAME,
        "name": AOI_NAME,
        "bbox": BBOX,
        "start": window_start.astimezone(timezone.utc).isoformat(),
        "end": window_end.astimezone(timezone.utc).isoformat(),
        "data_start": data_start.astimezone(timezone.utc).isoformat(),
        "data_end": data_end.astimezone(timezone.utc).isoformat(),
        "window_preset": window_preset,
        "current": current.astimezone(timezone.utc).isoformat(),
        "position_count": count,
        "loaded": count > 0,
    }


async def _load_bounds():
    factory = get_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                select(func.min(AisPosition.t), func.max(AisPosition.t), func.count())
            )
        ).one()
    t_min, t_max, count = row[0], row[1], row[2]
    if t_min is None or t_max is None or count == 0:
        t_min = parse_time(DEFAULT_START)
        t_max = parse_time(DEFAULT_END)
        count = 0
    return t_min, t_max, count


async def handle_replay_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    data_start, data_end, count = await _load_bounds()
    window_preset = REPLAY_DEFAULT_WINDOW_PRESET
    window_start, window_end = compute_window(data_start, data_end, window_preset)
    current = window_end
    playing = False
    speed = 1.0
    tick_interval = 0.5

    await websocket.send_json(
        _scenario_payload(
            data_start=data_start,
            data_end=data_end,
            window_start=window_start,
            window_end=window_end,
            window_preset=window_preset,
            count=count,
            current=current,
        )
    )

    if count > 0:
        factory = get_session_factory()
        async with factory() as session:
            await _send_frame(websocket, session, at=current, window_start=window_start)
        await websocket.send_json(
            {"type": "state", "current": current.isoformat(), "playing": playing}
        )

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=tick_interval)
                msg = json.loads(raw)
                action = msg.get("action")
                if action == "play":
                    playing = True
                    await websocket.send_json(
                        {"type": "state", "current": current.isoformat(), "playing": playing}
                    )
                elif action == "pause":
                    playing = False
                    await websocket.send_json(
                        {"type": "state", "current": current.isoformat(), "playing": playing}
                    )
                elif action == "seek":
                    target = parse_time(msg["t"])
                    current = max(window_start, min(window_end, target))
                    factory = get_session_factory()
                    async with factory() as session:
                        await _send_frame(
                            websocket, session, at=current, window_start=window_start
                        )
                    await websocket.send_json(
                        {"type": "state", "current": current.isoformat(), "playing": playing}
                    )
                elif action == "set_window":
                    window_preset = normalize_preset(msg.get("preset"))
                    window_start, window_end = compute_window(
                        data_start, data_end, window_preset
                    )
                    current = window_end
                    playing = False
                    factory = get_session_factory()
                    async with factory() as session:
                        await _send_frame(
                            websocket, session, at=current, window_start=window_start
                        )
                    await websocket.send_json(
                        _scenario_payload(
                            data_start=data_start,
                            data_end=data_end,
                            window_start=window_start,
                            window_end=window_end,
                            window_preset=window_preset,
                            count=count,
                            current=current,
                        )
                    )
                    await websocket.send_json(
                        {"type": "state", "current": current.isoformat(), "playing": playing}
                    )
                elif action == "speed":
                    speed = max(0.1, float(msg.get("multiplier", 1.0)))
            except asyncio.TimeoutError:
                pass

            if playing:
                window_tick_start = current
                window_tick_end = min(
                    window_end,
                    window_tick_start
                    + timedelta(seconds=REPLAY_SIM_SECONDS_PER_TICK * speed),
                )
                factory = get_session_factory()
                async with factory() as session:
                    await _send_frame(
                        websocket,
                        session,
                        at=window_tick_end,
                        window_start=window_start,
                    )
                current = window_tick_end
                if current >= window_end:
                    playing = False
                await websocket.send_json(
                    {"type": "state", "current": current.isoformat(), "playing": playing}
                )
    except WebSocketDisconnect:
        return
