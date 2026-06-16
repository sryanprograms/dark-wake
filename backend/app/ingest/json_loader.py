"""Load normalized AIS positions from JSON payload."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.ingest.ais_csv import filter_positions, normalize_digitraffic_feature


def is_live_snapshot_payload(payload: dict[str, Any]) -> bool:
    source = str(payload.get("source", "")).lower()
    return "live" in source or payload.get("live_snapshot") is True


def extract_positions_from_payload(payload: Any) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and "mmsi" in item and "lat" in item:
                positions.append(item)
    elif isinstance(payload, dict):
        if isinstance(payload.get("positions"), list):
            for item in payload["positions"]:
                if isinstance(item, dict) and "mmsi" in item and "lat" in item:
                    positions.append(item)
        elif payload.get("type") == "FeatureCollection" or "features" in payload:
            for feature in payload.get("features", []):
                pos = normalize_digitraffic_feature(feature)
                if pos:
                    positions.append(pos)
    return positions


def load_positions_from_json(
    path: Path,
    *,
    bbox: dict[str, float],
    start: datetime | None = None,
    end: datetime | None = None,
    live: bool = False,
) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and not live:
        live = is_live_snapshot_payload(payload)
    positions = extract_positions_from_payload(payload)
    if live:
        return filter_positions(positions, bbox, start=None, end=None)
    return filter_positions(positions, bbox, start, end)
