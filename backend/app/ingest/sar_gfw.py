"""Fetch SAR vessel detections from Global Fishing Watch 4Wings API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config.aoi import gfw_query_polygon_coords

GFW_BASE_URL = "https://gateway.api.globalfishingwatch.org"
SAR_DATASET = "public-global-sar-presence:latest"


def _parse_scene_time(raw: str) -> datetime:
    """Parse GFW report date strings like '2022-01-05 23:00'."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"unrecognized GFW date format: {raw!r}")


def _in_bbox(lat: float, lon: float, bbox: dict[str, float]) -> bool:
    return (
        bbox["min_lat"] <= lat <= bbox["max_lat"]
        and bbox["min_lon"] <= lon <= bbox["max_lon"]
    )


def parse_report_response(
    payload: dict[str, Any],
    bbox: dict[str, float],
) -> list[dict[str, Any]]:
    """Normalize GFW 4Wings SAR report JSON into detection records."""
    detections: list[dict[str, Any]] = []
    for entry in payload.get("entries", []):
        for dataset_key, rows in entry.items():
            if "sar-presence" not in dataset_key:
                continue
            if not rows:
                continue
            for row in rows:
                if not row:
                    continue
                lat_raw = row.get("lat")
                lon_raw = row.get("lon")
                date_raw = row.get("date")
                if lat_raw is None or lon_raw is None or date_raw is None:
                    continue
                lat = float(lat_raw)
                lon = float(lon_raw)
                if not _in_bbox(lat, lon, bbox):
                    continue
                scene_time = _parse_scene_time(str(date_raw))
                detections.append(
                    {
                        "t": scene_time.isoformat(),
                        "lat": lat,
                        "lon": lon,
                        "length_m": row.get("length"),
                        "scene_id": row.get("scene_id") or row.get("sceneId"),
                        "confidence": row.get("confidence"),
                        "detections": int(row.get("detections", 1)),
                        "entry_timestamp": row.get("entryTimestamp")
                        or row.get("entry_timestamp"),
                    }
                )
    return detections


def fetch_detections(
    bbox: dict[str, float],
    start: datetime,
    end: datetime,
    client: httpx.Client,
    *,
    token: str,
    polygon_coords: list[list[float]] | None = None,
) -> list[dict[str, Any]]:
    """Pull SAR detections for a bbox and time window via GFW 4Wings report API."""
    if polygon_coords is None:
        polygon_coords = gfw_query_polygon_coords()

    start_s = start.strftime("%Y-%m-%d")
    end_s = end.strftime("%Y-%m-%d")
    params = {
        "spatial-resolution": "HIGH",
        "temporal-resolution": "HOURLY",
        "spatial-aggregation": "false",
        "datasets[0]": SAR_DATASET,
        "date-range": f"{start_s},{end_s}",
        "format": "JSON",
    }
    body = {"geojson": {"type": "Polygon", "coordinates": [polygon_coords]}}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    response = client.post(
        f"{GFW_BASE_URL}/v3/4wings/report",
        params=params,
        json=body,
        headers=headers,
        timeout=120.0,
    )
    response.raise_for_status()
    return parse_report_response(response.json(), bbox)
