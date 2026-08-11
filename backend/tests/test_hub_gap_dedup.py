"""Regression: gap alerts must be detected/persisted exactly once.

The shared AIS ingest service fans every update out to both the TimelineHub
and the (legacy) LiveHub. Both hubs used to run their own gap detection and
persistence, so each AIS update produced duplicate persisted alerts.
"""

from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.live.hub as live_hub_module
import app.timeline.hub as timeline_hub_module
from app.config.thresholds import GAP_MIN_S
from app.ingest.ais_ingest import AisIngestService
from app.live.hub import LiveHub
from app.timeline.hub import TimelineHub


class _SessionCtx:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return None


def _mock_session_factory() -> MagicMock:
    factory = MagicMock()
    factory.return_value = _SessionCtx()
    return factory


@pytest.mark.asyncio
async def test_gap_alert_persisted_once_across_hubs() -> None:
    ingest = AisIngestService()
    timeline_hub = TimelineHub()
    live_hub = LiveHub()

    # Wire both hubs to the shared ingest service exactly as start() does.
    ingest.on_update(timeline_hub._handle_ais_update)
    ingest.on_update(live_hub._handle_update)

    mmsi = 123456
    stale = datetime.now(timezone.utc) - timedelta(seconds=GAP_MIN_S + 120)
    # Force a resume-worthy gap in any hub that still tracks ingest times.
    for hub in (timeline_hub, live_hub):
        if hasattr(hub, "_last_ingest_at"):
            hub._last_ingest_at[mmsi] = stale

    update = {
        "kind": "position",
        "mmsi": mmsi,
        "t": datetime.now(timezone.utc),
        "lat": 59.5,
        "lon": 24.0,
        "sog": 5.0,
        "cog": 90.0,
        "heading": 88.0,
    }

    persist = AsyncMock(return_value=1)
    # Patch persistence + session factory in whichever hub modules still own it,
    # so this stays a valid regression guard even if LiveHub regains gap logic.
    with ExitStack() as stack:
        for module in (timeline_hub_module, live_hub_module):
            if hasattr(module, "persist_operator_event"):
                stack.enter_context(
                    patch.object(module, "persist_operator_event", persist)
                )
            if hasattr(module, "get_session_factory"):
                stack.enter_context(
                    patch.object(
                        module, "get_session_factory", return_value=_mock_session_factory()
                    )
                )
        for handler in list(ingest._update_handlers):
            await handler(update)

    assert persist.await_count == 1
