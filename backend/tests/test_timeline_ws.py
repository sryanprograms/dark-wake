"""Tests for unified /ws/timeline WebSocket."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.websockets import WebSocketState

from app.api.timeline_ws import handle_timeline_ws
from app.replay.clock import parse_time
from app.timeline.hub import TimelineHub, get_timeline_hub

DATA_START = parse_time("2022-06-01T00:00:00Z")
DATA_END = parse_time("2022-06-02T00:00:00Z")


class _SessionCtx:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args) -> None:
        return None


def _mock_session_factory(session: AsyncMock | None = None) -> MagicMock:
    session = session or AsyncMock()
    factory = MagicMock()
    factory.return_value = _SessionCtx(session)
    return factory


@pytest.fixture
def hub() -> TimelineHub:
    timeline_hub = TimelineHub()
    timeline_hub.data_start = DATA_START
    timeline_hub.data_end = DATA_END
    timeline_hub._scenes = [
        {
            "id": 1,
            "t": "2022-06-17T04:00:00Z",
            "scene_id": "scene-abc",
            "detection_count": 3,
            "dark_count": 1,
        }
    ]
    return timeline_hub


@pytest.fixture
def timeline_app(hub: TimelineHub, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr("app.timeline.hub._hub", hub)
    monkeypatch.setattr("app.api.timeline_ws.get_timeline_hub", lambda: hub)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield

    app = FastAPI(lifespan=lifespan)
    app.websocket("/ws/timeline")(handle_timeline_ws)
    return app


@pytest.fixture
def client(timeline_app: FastAPI) -> TestClient:
    return TestClient(timeline_app)


@pytest.mark.asyncio
async def test_subscribe_sends_timeline_state(hub: TimelineHub) -> None:
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED

    with patch("app.timeline.hub.get_session_factory", return_value=_mock_session_factory()):
        with patch("app.timeline.hub.load_timeline_bounds", new=AsyncMock(return_value=(DATA_START, DATA_END, 2, 0))):
            with patch("app.timeline.hub.load_scenes", new=AsyncMock(return_value=hub._scenes)):
                client = await hub.subscribe(ws)

    assert client.mode == "live"
    first_call = ws.send_json.await_args_list[0].args[0]
    assert first_call["type"] == "timeline_state"
    assert first_call["mode"] == "live"
    assert first_call["data_start"] == DATA_START.isoformat()
    assert first_call["data_end"] == DATA_END.isoformat()
    assert first_call["scenes"] == hub._scenes
    assert first_call["playhead"] is not None


@pytest.mark.asyncio
async def test_seek_historical_frame(hub: TimelineHub) -> None:
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    seek_at = parse_time("2022-06-01T12:00:00Z")
    snapshot = [
        {
            "type": "ais",
            "mmsi": 123,
            "t": seek_at.isoformat(),
            "lat": 59.5,
            "lon": 24.0,
            "sog": 5.0,
            "cog": 90.0,
            "heading": 88.0,
            "name": "TESTER",
            "ship_type": "Tanker",
            "flag": "FI",
            "country": "Finland",
        }
    ]
    tracks = [{"mmsi": 123, "path": [[24.0, 59.4], [24.0, 59.5]]}]

    with patch("app.timeline.hub.get_session_factory", return_value=_mock_session_factory()):
        with patch("app.timeline.hub.load_timeline_bounds", new=AsyncMock(return_value=(DATA_START, DATA_END, 2, 0))):
            with patch("app.timeline.hub.load_scenes", new=AsyncMock(return_value=[])):
                with patch("app.timeline.hub.fetch_snapshot_at", new=AsyncMock(return_value=snapshot)):
                    with patch("app.timeline.hub.fetch_tracks_up_to", new=AsyncMock(return_value=tracks)):
                        client = await hub.subscribe(ws)
                        await hub._seek(client, "2022-06-01T12:00:00Z")

    assert client.mode == "historical"
    assert client.playhead == seek_at
    sent_types = [call.args[0]["type"] for call in ws.send_json.await_args_list]
    assert "timeline_state" in sent_types
    assert "ais" in sent_types
    assert "tracks_batch" in sent_types
    state_msgs = [c.args[0] for c in ws.send_json.await_args_list if c.args[0]["type"] == "state"]
    assert state_msgs[-1]["mode"] == "historical"
    assert state_msgs[-1]["playing"] is False


@pytest.mark.asyncio
async def test_snap_scene_sends_scene_frame_with_historical_ais(hub: TimelineHub) -> None:
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    scene_at = parse_time("2022-06-17T04:00:00Z")
    frame = {
        "type": "scene_frame",
        "scene_id": "1",
        "t": scene_at.isoformat(),
        "ais": [
            {
                "mmsi": 123,
                "t": scene_at.isoformat(),
                "lat": 59.5,
                "lon": 24.0,
                "sog": 5.0,
                "cog": 90.0,
            }
        ],
        "sar": [{"id": "10", "t": scene_at.isoformat(), "lat": 59.51, "lon": 24.01}],
        "contacts": [],
    }
    tracks = [{"mmsi": 123, "path": [[24.0, 59.4], [24.0, 59.5]]}]

    with patch("app.timeline.hub.get_session_factory", return_value=_mock_session_factory()):
        with patch("app.timeline.hub.load_timeline_bounds", new=AsyncMock(return_value=(DATA_START, DATA_END, 2, 1))):
            with patch("app.timeline.hub.load_scenes", new=AsyncMock(return_value=hub._scenes)):
                with patch("app.timeline.hub.build_scene_frame", new=AsyncMock(return_value=frame)):
                    with patch("app.timeline.hub.fetch_tracks_up_to", new=AsyncMock(return_value=tracks)):
                        client = await hub.subscribe(ws)
                        await hub._snap_scene(client, 1)

    assert client.mode == "scene"
    assert client.scene_id == 1
    scene_msgs = [c.args[0] for c in ws.send_json.await_args_list if c.args[0].get("type") == "scene_frame"]
    assert len(scene_msgs) == 1
    assert scene_msgs[0]["ais"][0]["mmsi"] == 123
    assert scene_msgs[0]["tracks"] == tracks


@pytest.mark.asyncio
async def test_go_live_restores_live_mode(hub: TimelineHub) -> None:
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    hub.registry.apply_position(
        {
            "mmsi": 999,
            "t": datetime(2022, 6, 1, 8, 0, tzinfo=timezone.utc),
            "lat": 59.8,
            "lon": 24.5,
            "sog": 10.0,
            "cog": 180.0,
            "heading": 180.0,
        }
    )

    with patch("app.timeline.hub.get_session_factory", return_value=_mock_session_factory()):
        with patch("app.timeline.hub.load_timeline_bounds", new=AsyncMock(return_value=(DATA_START, DATA_END, 2, 0))):
            with patch("app.timeline.hub.load_scenes", new=AsyncMock(return_value=[])):
                client = await hub.subscribe(ws)
                client.mode = "historical"
                await hub._go_live(client)

    assert client.mode == "live"
    assert client.playing is False
    state_msgs = [c.args[0] for c in ws.send_json.await_args_list if c.args[0]["type"] == "state"]
    assert state_msgs[-1]["mode"] == "live"


def test_ws_connect_and_go_live(client: TestClient, hub: TimelineHub) -> None:
    with patch("app.timeline.hub.get_session_factory", return_value=_mock_session_factory()):
        with patch("app.timeline.hub.load_timeline_bounds", new=AsyncMock(return_value=(DATA_START, DATA_END, 2, 0))):
            with patch("app.timeline.hub.load_scenes", new=AsyncMock(return_value=hub._scenes)):
                with client.websocket_connect("/ws/timeline") as ws:
                    msg = ws.receive_json()
                    assert msg["type"] == "timeline_state"
                    assert msg["mode"] == "live"

                    ws.send_json({"action": "go_live"})
                    while True:
                        nxt = ws.receive_json()
                        if nxt["type"] == "state":
                            assert nxt["mode"] == "live"
                            break


def test_ws_seek(client: TestClient, hub: TimelineHub) -> None:
    snapshot = [
        {
            "type": "ais",
            "mmsi": 456,
            "t": "2022-06-01T06:00:00Z",
            "lat": 59.6,
            "lon": 24.1,
            "sog": 4.0,
            "cog": 45.0,
            "heading": 45.0,
            "name": None,
            "ship_type": None,
            "flag": "EE",
            "country": "Estonia",
        }
    ]

    with patch("app.timeline.hub.get_session_factory", return_value=_mock_session_factory()):
        with patch("app.timeline.hub.load_timeline_bounds", new=AsyncMock(return_value=(DATA_START, DATA_END, 2, 0))):
            with patch("app.timeline.hub.load_scenes", new=AsyncMock(return_value=[])):
                with patch("app.timeline.hub.fetch_snapshot_at", new=AsyncMock(return_value=snapshot)):
                    with patch("app.timeline.hub.fetch_tracks_up_to", new=AsyncMock(return_value=[])):
                        with client.websocket_connect("/ws/timeline") as ws:
                            assert ws.receive_json()["type"] == "timeline_state"
                            # initial state message after subscribe
                            while True:
                                nxt = ws.receive_json()
                                if nxt["type"] == "state":
                                    break

                            ws.send_json({"action": "seek", "t": "2022-06-01T06:00:00Z"})
                            seen: set[str] = set()
                            while len(seen) < 4:
                                msg = ws.receive_json()
                                seen.add(msg["type"])
                            assert "timeline_state" in seen
                            assert "ais" in seen
                            assert "tracks_batch" in seen
                            assert "state" in seen


@pytest.mark.asyncio
async def test_client_uses_refreshed_bounds_after_persist(hub: TimelineHub) -> None:
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    extended_end = parse_time("2022-06-05T00:00:00Z")
    seek_target = "2022-06-03T00:00:00Z"

    with patch("app.timeline.hub.get_session_factory", return_value=_mock_session_factory()):
        with patch("app.timeline.hub.load_scenes", new=AsyncMock(return_value=[])):
            with patch(
                "app.timeline.hub.load_timeline_bounds",
                new=AsyncMock(return_value=(DATA_START, DATA_END, 2, 0)),
            ):
                client = await hub.subscribe(ws)

            # New AIS data lands after subscribe and extends the timeline end.
            with patch(
                "app.timeline.hub.load_timeline_bounds",
                new=AsyncMock(return_value=(DATA_START, extended_end, 5, 0)),
            ):
                await hub._on_ais_persisted(True)
                with patch("app.timeline.hub.fetch_snapshot_at", new=AsyncMock(return_value=[])):
                    with patch("app.timeline.hub.fetch_tracks_up_to", new=AsyncMock(return_value=[])):
                        await hub._seek(client, seek_target)

    ts_msgs = [
        c.args[0] for c in ws.send_json.await_args_list if c.args[0]["type"] == "timeline_state"
    ]
    # timeline_state must advertise the refreshed end, not the value cached at subscribe.
    assert ts_msgs[-1]["data_end"] == extended_end.isoformat()
    # Seeking past the old end but within the refreshed end must not be clamped to stale bounds.
    assert client.playhead == parse_time(seek_target)


@pytest.mark.asyncio
async def test_snap_scene_invalid_leaves_mode_unchanged(hub: TimelineHub) -> None:
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    invalid_frame = {"type": "scene_frame", "scene_id": "999", "t": None}

    with patch("app.timeline.hub.get_session_factory", return_value=_mock_session_factory()):
        with patch(
            "app.timeline.hub.load_timeline_bounds",
            new=AsyncMock(return_value=(DATA_START, DATA_END, 2, 0)),
        ):
            with patch("app.timeline.hub.load_scenes", new=AsyncMock(return_value=[])):
                client = await hub.subscribe(ws)
                assert client.mode == "live"
                with patch(
                    "app.timeline.hub.build_scene_frame",
                    new=AsyncMock(return_value=invalid_frame),
                ):
                    await hub._snap_scene(client, 999)

    assert client.mode == "live"
    assert client.scene_id is None


def test_get_timeline_hub_singleton() -> None:
    from app.timeline import hub as hub_module

    hub_module._hub = None
    assert get_timeline_hub() is get_timeline_hub()
