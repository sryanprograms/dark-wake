"""Submarine telecommunication cable routes from TeleGeography."""

from __future__ import annotations

import time
from typing import Any

import httpx

TELEGEOGRAPHY_CABLE_GEO_URL = (
    "https://www.submarinecablemap.com/api/v3/cable/cable-geo.json"
)

_CACHE_TTL_S = 3600
_cache: dict[str, Any] = {"fetched_at": 0.0, "features": []}


def _parse_hex_color(value: str | None) -> list[int] | None:
    if not value or not value.startswith("#") or len(value) != 7:
        return None
    try:
        return [int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16), 220]
    except ValueError:
        return None


def _coords_in_bbox(
    coordinates: list[list[float]],
    bbox: dict[str, float],
) -> bool:
    min_lon = bbox["min_lon"]
    max_lon = bbox["max_lon"]
    min_lat = bbox["min_lat"]
    max_lat = bbox["max_lat"]
    for lon, lat in coordinates:
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            return True
    return False


def _segments_from_geometry(geometry: dict[str, Any]) -> list[list[list[float]]]:
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")
    if not coords:
        return []
    if geom_type == "LineString":
        return [coords]
    if geom_type == "MultiLineString":
        return coords
    return []


def parse_cable_features(
    payload: dict[str, Any],
    bbox: dict[str, float],
) -> list[dict[str, Any]]:
    """Filter TeleGeography GeoJSON to cable segments intersecting bbox."""
    cables: list[dict[str, Any]] = []
    for feature in payload.get("features", []):
        if not feature:
            continue
        props = feature.get("properties") or {}
        cable_id = props.get("id") or props.get("feature_id") or "unknown"
        name = (props.get("name") or cable_id).strip()
        color = _parse_hex_color(props.get("color"))
        for segment_idx, segment in enumerate(_segments_from_geometry(feature.get("geometry") or {})):
            if not segment or not _coords_in_bbox(segment, bbox):
                continue
            cables.append(
                {
                    "id": f"{cable_id}-{segment_idx}",
                    "cable_id": cable_id,
                    "name": name,
                    "path": segment,
                    "color": color,
                }
            )
    cables.sort(key=lambda c: (c["name"].lower(), c["id"]))
    return cables


def fetch_cable_geojson(client: httpx.Client) -> dict[str, Any]:
    response = client.get(TELEGEOGRAPHY_CABLE_GEO_URL, timeout=120.0)
    response.raise_for_status()
    return response.json()


def _cached_features(client: httpx.Client) -> list[dict[str, Any]]:
    now = time.monotonic()
    if _cache["features"] and now - _cache["fetched_at"] < _CACHE_TTL_S:
        return _cache["features"]
    payload = fetch_cable_geojson(client)
    _cache["features"] = payload.get("features", [])
    _cache["fetched_at"] = now
    return _cache["features"]


def fetch_cables_in_bbox(
    bbox: dict[str, float],
    *,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Return cable path segments whose routes pass through bbox."""
    owns_client = client is None
    if owns_client:
        client = httpx.Client()
    try:
        features = _cached_features(client)
        return parse_cable_features({"features": features}, bbox)
    finally:
        if owns_client:
            client.close()
