"""Shared Digitraffic AIS fetch helpers."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.ingest.ais_csv import filter_positions, normalize_digitraffic_feature
from app.ingest.vessel_meta import country_from_mmsi, flag_from_mmsi, ship_type_label

DIGITRAFFIC_LOCATIONS_URL = "https://meri.digitraffic.fi/api/ais/v1/locations"
DIGITRAFFIC_VESSELS_URL = "https://meri.digitraffic.fi/api/ais/v1/vessels"


def fetch_digitraffic_vessel_metadata(
    client: httpx.Client,
    *,
    user_agent: str,
) -> dict[int, dict]:
    """Static vessel metadata keyed by MMSI (name, shipType, callsign, imo)."""
    headers = {
        "Accept-Encoding": "gzip",
        "Digitraffic-User": user_agent,
    }
    response = client.get(DIGITRAFFIC_VESSELS_URL, headers=headers, timeout=120.0)
    response.raise_for_status()
    payload = response.json()
    out: dict[int, dict] = {}
    for item in payload:
        mmsi = item.get("mmsi")
        if mmsi is None:
            continue
        out[int(mmsi)] = item
    return out


def enrich_positions_with_metadata(
    positions: list[dict],
    metadata: dict[int, dict],
) -> None:
    """Attach name, ship_type, flag, and country to position dicts in place."""
    for pos in positions:
        mmsi = int(pos["mmsi"])
        meta = metadata.get(mmsi, {})
        if not pos.get("name"):
            name = (meta.get("name") or "").strip()
            if name:
                pos["name"] = name
        ship_type_code = meta.get("shipType")
        if ship_type_code is not None:
            pos["ship_type"] = ship_type_label(ship_type_code)
        if meta.get("callSign"):
            pos["callsign"] = meta["callSign"]
        if meta.get("imo"):
            pos["imo"] = meta["imo"]
        pos["flag"] = flag_from_mmsi(mmsi)
        pos["country"] = country_from_mmsi(mmsi)


def fetch_digitraffic_positions(
    client: httpx.Client,
    *,
    user_agent: str,
    bbox: dict[str, float],
    start: datetime | None = None,
    end: datetime | None = None,
    live_snapshot: bool = False,
    enrich_metadata: bool = False,
) -> list[dict]:
    headers = {
        "Accept-Encoding": "gzip",
        "Digitraffic-User": user_agent,
    }
    response = client.get(DIGITRAFFIC_LOCATIONS_URL, headers=headers, timeout=60.0)
    response.raise_for_status()
    payload = response.json()
    snapshot_time = datetime.now(timezone.utc) if live_snapshot else None
    positions: list[dict] = []
    for feature in payload.get("features", []):
        pos = normalize_digitraffic_feature(feature, default_time=snapshot_time)
        if pos:
            positions.append(pos)
    if live_snapshot:
        filtered = filter_positions(positions, bbox, start=None, end=None)
    else:
        filtered = filter_positions(positions, bbox, start, end)
    if enrich_metadata and filtered:
        metadata = fetch_digitraffic_vessel_metadata(client, user_agent=user_agent)
        enrich_positions_with_metadata(filtered, metadata)
    return filtered
