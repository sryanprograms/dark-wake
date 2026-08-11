"""Tests for AISStream → PostGIS persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.config.settings import Settings
from app.ingest.ais_persist import AisPersistBuffer, _flush_sync

T0 = datetime(2024, 6, 17, 12, 0, tzinfo=timezone.utc)


def _settings(**overrides) -> Settings:
    base = Settings(
        database_url="postgresql://darkwake:darkwake@localhost:5432/darkwake",
        gfw_api_token="",
        aisstream_api_key="test-key",
        digitraffic_user="test",
        live_track_buffer_hours=6.0,
        sar_poll_interval_s=3600,
        ais_persist_enabled=True,
        ais_persist_flush_interval_s=15,
        ais_persist_min_interval_s=60,
    )
    return Settings(**{**base.__dict__, **overrides})


def _position(mmsi: int, offset_s: int = 0) -> dict:
    return {
        "kind": "position",
        "mmsi": mmsi,
        "t": T0 + timedelta(seconds=offset_s),
        "lat": 55.5,
        "lon": 12.0,
        "sog": 10.0,
        "cog": 90.0,
        "heading": 88.0,
        "name": "TEST SHIP",
        "ship_type": "Cargo",
        "flag": "DK",
    }


@pytest.mark.asyncio
async def test_persist_buffer_samples_per_vessel_interval() -> None:
    buffer = AisPersistBuffer(_settings(ais_persist_min_interval_s=60))
    await buffer.offer(_position(111, 0))
    await buffer.offer(_position(111, 30))
    await buffer.offer(_position(111, 90))
    await buffer.offer(_position(222, 0))

    async with buffer._lock:
        pending = list(buffer._pending_positions)
    assert len(pending) == 3
    assert {p["mmsi"] for p in pending} == {111, 222}


@pytest.mark.asyncio
async def test_persist_buffer_flush_calls_loader() -> None:
    buffer = AisPersistBuffer(_settings())
    await buffer.offer(_position(111, 0))

    with patch("app.ingest.ais_persist._flush_sync", return_value={"vessels": 1, "positions": 1}):
        counts = await buffer.flush()

    assert counts == {"vessels": 1, "positions": 1}


@pytest.mark.asyncio
async def test_flush_retains_pending_on_failure() -> None:
    buffer = AisPersistBuffer(_settings())
    await buffer.offer(_position(111, 0))
    await buffer.offer({"kind": "static", "mmsi": 222, "name": "STATIC", "ship_type": "Tanker"})

    with patch("app.ingest.ais_persist._flush_sync", side_effect=RuntimeError("db down")):
        counts = await buffer.flush()

    assert counts == {"vessels": 0, "positions": 0}

    async with buffer._lock:
        pending_positions = list(buffer._pending_positions)
        pending_static = dict(buffer._pending_static)

    assert len(pending_positions) == 1
    assert pending_positions[0]["mmsi"] == 111
    assert 222 in pending_static


def test_flush_sync_delegates_to_loader() -> None:
    positions = [
        {
            "mmsi": 111,
            "t": T0.isoformat(),
            "lat": 55.5,
            "lon": 12.0,
            "sog": 10.0,
            "cog": 90.0,
            "heading": 88.0,
            "name": "TEST",
        }
    ]
    static = [{"mmsi": 222, "name": "STATIC", "ship_type": "Tanker"}]

    with patch("app.ingest.ais_persist.connect") as connect_mock:
        conn = connect_mock.return_value
        with patch("app.ingest.ais_persist.upsert_vessels", return_value=1) as upsert:
            with patch(
                "app.ingest.ais_persist.load_positions",
                return_value={"vessels": 1, "positions": 1},
            ) as load:
                counts = _flush_sync("postgresql://x", positions, static)

    assert counts == {"vessels": 1, "positions": 1}
    upsert.assert_called_once_with(conn, static)
    load.assert_called_once_with(conn, positions)
