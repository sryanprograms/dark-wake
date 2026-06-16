"""Normalize AIS position records from CSV and JSON sources."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Iterable

from app.ingest.vessel_meta import country_from_mmsi, flag_from_mmsi, ship_type_label

DMA_COLUMNS = {
    "timestamp": "Timestamp",
    "mmsi": "MMSI",
    "lat": "Latitude",
    "lon": "Longitude",
    "sog": "SOG",
    "cog": "COG",
    "heading": "Heading",
    "name": "Name",
    "ship_type": "Ship type",
}


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_dma_timestamp(raw: str) -> datetime:
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"unrecognized DMA timestamp: {raw!r}")


def _parse_iso_timestamp(raw: str | int | float) -> datetime:
    if isinstance(raw, (int, float)):
        # Digitraffic uses epoch seconds; metadata may use ms — callers pass seconds.
        return datetime.fromtimestamp(float(raw), tz=timezone.utc)
    text = str(raw).strip()
    if text.isdigit():
        ts = int(text)
        if ts > 1_000_000_000_000:
            ts //= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _in_bbox(lat: float, lon: float, bbox: dict[str, float]) -> bool:
    return (
        bbox["min_lat"] <= lat <= bbox["max_lat"]
        and bbox["min_lon"] <= lon <= bbox["max_lon"]
    )


def normalize_dma_row(row: dict[str, str]) -> dict[str, Any] | None:
    lat = _parse_float(row.get(DMA_COLUMNS["lat"]))
    lon = _parse_float(row.get(DMA_COLUMNS["lon"]))
    mmsi = _parse_int(row.get(DMA_COLUMNS["mmsi"]))
    ts_raw = row.get(DMA_COLUMNS["timestamp"])
    if lat is None or lon is None or mmsi is None or not ts_raw:
        return None
    ship_type_raw = (row.get(DMA_COLUMNS["ship_type"]) or "").strip()
    ship_type = ship_type_label(ship_type_raw) if ship_type_raw else None
    return {
        "mmsi": mmsi,
        "t": _parse_dma_timestamp(ts_raw).isoformat(),
        "lat": lat,
        "lon": lon,
        "sog": _parse_float(row.get(DMA_COLUMNS["sog"])),
        "cog": _parse_float(row.get(DMA_COLUMNS["cog"])),
        "heading": _parse_float(row.get(DMA_COLUMNS["heading"])),
        "name": (row.get(DMA_COLUMNS["name"]) or "").strip() or None,
        "ship_type": ship_type,
        "flag": flag_from_mmsi(mmsi),
        "country": country_from_mmsi(mmsi),
    }


def normalize_baltic_row(row: dict[str, str]) -> dict[str, Any] | None:
    """IEEE Baltic Sea AIS CSV: timestamp,mmsi,lat,lon,speed,course,heading,..."""
    lat = _parse_float(row.get("lat"))
    lon = _parse_float(row.get("lon"))
    mmsi = _parse_int(row.get("mmsi"))
    ts_raw = row.get("timestamp")
    if lat is None or lon is None or mmsi is None or not ts_raw:
        return None
    speed = _parse_float(row.get("speed"))
    sog = speed * 1.94384 if speed is not None else None  # m/s → knots
    return {
        "mmsi": mmsi,
        "t": _parse_iso_timestamp(ts_raw).isoformat(),
        "lat": lat,
        "lon": lon,
        "sog": sog,
        "cog": _parse_float(row.get("course")),
        "heading": _parse_float(row.get("heading")),
        "name": None,
    }


def _digitraffic_timestamp(
    props: dict[str, Any],
    *,
    default_time: datetime | None = None,
) -> datetime | None:
    ext = props.get("timestampExternal")
    if ext is not None:
        try:
            ext_i = int(ext)
            if ext_i > 1_000_000_000_000:
                return datetime.fromtimestamp(ext_i / 1000, tz=timezone.utc)
            if ext_i > 1_000_000_000:
                return datetime.fromtimestamp(ext_i, tz=timezone.utc)
        except (TypeError, ValueError):
            pass
    for key in ("time", "timestamp"):
        raw = props.get(key)
        if raw is None:
            continue
        try:
            ts = int(raw)
        except (TypeError, ValueError):
            continue
        if ts > 1_000_000_000:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    return default_time


def normalize_digitraffic_feature(
    feature: dict[str, Any],
    *,
    default_time: datetime | None = None,
) -> dict[str, Any] | None:
    props = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates") or []
    if len(coords) < 2:
        return None
    lon, lat = float(coords[0]), float(coords[1])
    mmsi = _parse_int(feature.get("mmsi") or props.get("mmsi"))
    ts = _digitraffic_timestamp(props, default_time=default_time)
    if mmsi is None or ts is None:
        return None
    return {
        "mmsi": mmsi,
        "t": ts.isoformat(),
        "lat": lat,
        "lon": lon,
        "sog": _parse_float(props.get("sog")),
        "cog": _parse_float(props.get("cog")),
        "heading": _parse_float(props.get("heading")),
        "name": (props.get("name") or "").strip() or None,
        "flag": flag_from_mmsi(mmsi),
        "country": country_from_mmsi(mmsi),
    }


def filter_positions(
    positions: Iterable[dict[str, Any]],
    bbox: dict[str, float],
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pos in positions:
        lat = float(pos["lat"])
        lon = float(pos["lon"])
        if not _in_bbox(lat, lon, bbox):
            continue
        t = datetime.fromisoformat(pos["t"])
        if start and t < start:
            continue
        if end and t > end:
            continue
        out.append(pos)
    return out


def load_positions_from_csv(
    path: Path,
    *,
    format: str,
    bbox: dict[str, float],
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    normalizer = normalize_dma_row if format == "dma" else normalize_baltic_row
    positions: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pos = normalizer(row)
            if pos:
                positions.append(pos)
    return filter_positions(positions, bbox, start, end)


def load_positions_from_json(
    path: Path,
    *,
    bbox: dict[str, float],
    start: datetime | None = None,
    end: datetime | None = None,
    live: bool = False,
) -> list[dict[str, Any]]:
    from app.ingest.json_loader import load_positions_from_json as _load

    return _load(path, bbox=bbox, start=start, end=end, live=live)


def parse_dma_csv_text(
    text: str,
    bbox: dict[str, float],
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    reader = csv.DictReader(StringIO(text))
    for row in reader:
        pos = normalize_dma_row(row)
        if pos:
            positions.append(pos)
    return filter_positions(positions, bbox, start, end)
