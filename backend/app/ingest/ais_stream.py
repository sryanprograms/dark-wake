"""AISStream.io WebSocket message parsing and subscription helpers."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.config.aoi import aisstream_bounding_boxes
from app.ingest.vessel_meta import country_from_mmsi, flag_from_mmsi, ship_type_label

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"

_TIME_UTC_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}(?:\.\d+)?)"
)


def build_subscription_message(api_key: str) -> dict[str, Any]:
    return {
        "APIKey": api_key,
        "BoundingBoxes": aisstream_bounding_boxes(),
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }


def parse_time_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    match = _TIME_UTC_RE.match(value.strip())
    if not match:
        return None
    text = f"{match.group(1)}T{match.group(2)}"
    try:
        return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _metadata_fields(message: dict[str, Any]) -> dict[str, Any]:
    meta = message.get("MetaData") or {}
    mmsi = meta.get("MMSI")
    if mmsi is None:
        return {}
    mmsi_int = int(mmsi)
    name = (meta.get("ShipName") or "").strip() or None
    return {
        "mmsi": mmsi_int,
        "name": name,
        "flag": flag_from_mmsi(mmsi_int),
        "country": country_from_mmsi(mmsi_int),
        "t": parse_time_utc(meta.get("time_utc")),
    }


def parse_position_report(message: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize an AISStream PositionReport envelope to an internal position dict."""
    if message.get("MessageType") != "PositionReport":
        return None
    report = (message.get("Message") or {}).get("PositionReport")
    if not report:
        return None

    meta = _metadata_fields(message)
    mmsi = meta.get("mmsi") or report.get("UserID")
    if mmsi is None:
        return None
    mmsi_int = int(mmsi)

    lat = report.get("Latitude", meta.get("latitude"))
    lon = report.get("Longitude", meta.get("longitude"))
    if lat is None or lon is None:
        return None

    reported_at = meta.get("t") or datetime.now(timezone.utc)
    return {
        "kind": "position",
        "mmsi": mmsi_int,
        "t": reported_at,
        "lat": float(lat),
        "lon": float(lon),
        "sog": _optional_float(report.get("Sog")),
        "cog": _optional_float(report.get("Cog")),
        "heading": _optional_float(report.get("TrueHeading")),
        "nav_status": _nav_status_label(report.get("NavigationalStatus")),
        "name": meta.get("name"),
        "ship_type": None,
        "flag": meta.get("flag") or flag_from_mmsi(mmsi_int),
        "country": meta.get("country") or country_from_mmsi(mmsi_int),
    }


def parse_ship_static(message: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize ShipStaticData to vessel metadata update."""
    if message.get("MessageType") != "ShipStaticData":
        return None
    static = (message.get("Message") or {}).get("ShipStaticData")
    if not static:
        return None

    meta = _metadata_fields(message)
    mmsi = meta.get("mmsi") or static.get("UserID")
    if mmsi is None:
        return None
    mmsi_int = int(mmsi)

    name = (static.get("Name") or meta.get("name") or "").strip() or None
    ship_type_code = static.get("Type")
    ship_type = ship_type_label(ship_type_code) if ship_type_code is not None else None

    return {
        "kind": "static",
        "mmsi": mmsi_int,
        "t": meta.get("t") or datetime.now(timezone.utc),
        "name": name,
        "ship_type": ship_type,
        "callsign": (static.get("Callsign") or "").strip() or None,
        "imo": static.get("ImoNumber"),
        "length_m": _dimension_m(static),
        "flag": meta.get("flag") or flag_from_mmsi(mmsi_int),
        "country": meta.get("country") or country_from_mmsi(mmsi_int),
    }


def parse_aisstream_message(message: dict[str, Any]) -> dict[str, Any] | None:
    """Return a normalized position or static update, or None if not handled."""
    message_type = message.get("MessageType")
    if message_type == "PositionReport":
        return parse_position_report(message)
    if message_type == "ShipStaticData":
        return parse_ship_static(message)
    return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dimension_m(static: dict[str, Any]) -> float | None:
    to_bow = static.get("DimensionToBow") or 0
    to_stern = static.get("DimensionToStern") or 0
    total = to_bow + to_stern
    return float(total) if total > 0 else None


_NAV_STATUS_LABELS = {
    0: "under way",
    1: "at anchor",
    2: "not under command",
    3: "restricted manoeuvrability",
    4: "constrained by draught",
    5: "moored",
    6: "aground",
    7: "engaged in fishing",
    8: "under way sailing",
    15: "undefined",
}


def _nav_status_label(code: Any) -> str | None:
    if code is None:
        return None
    try:
        return _NAV_STATUS_LABELS.get(int(code), f"status_{int(code)}")
    except (TypeError, ValueError):
        return None
