"""Persist operator-facing events to PostGIS."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def persist_operator_event(
    session: AsyncSession,
    *,
    event: dict[str, Any],
    track_excerpt: list[dict[str, Any]] | None = None,
) -> int:
    lat = event.get("lat")
    lon = event.get("lon")
    geom_sql = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)" if lat is not None and lon is not None else "NULL"

    result = await session.execute(
        text(
            f"""
            INSERT INTO operator_event (
                kind, severity, mmsi, t, title, reason, details, geom, track_excerpt
            ) VALUES (
                :kind, :severity, :mmsi, :t, :title, :reason, :details::jsonb,
                {geom_sql},
                :track_excerpt::jsonb
            )
            RETURNING id
            """
        ),
        {
            "kind": event["kind"],
            "severity": event["severity"],
            "mmsi": event.get("mmsi"),
            "t": event["t"],
            "title": event["title"],
            "reason": event.get("reason"),
            "details": json.dumps(event.get("details") or {}),
            "lon": lon,
            "lat": lat,
            "track_excerpt": json.dumps(track_excerpt or []),
        },
    )
    await session.commit()
    row = result.one()
    return int(row[0])
