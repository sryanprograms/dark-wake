"""In-memory vessel registry with rolling track buffers for live mode."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class PositionPoint:
    t: datetime
    lat: float
    lon: float
    sog: float | None = None
    cog: float | None = None
    heading: float | None = None


@dataclass
class VesselState:
    mmsi: int
    latest: PositionPoint | None = None
    name: str | None = None
    ship_type: str | None = None
    flag: str | None = None
    country: str | None = None
    nav_status: str | None = None
    track: deque[PositionPoint] = field(default_factory=deque)
    last_gap_alert_at: datetime | None = None
    last_ingest_at: datetime | None = None
    gap_monitor: bool = False


class VesselRegistry:
    def __init__(self, *, track_max_age: timedelta) -> None:
        self._track_max_age = track_max_age
        self._vessels: dict[int, VesselState] = {}

    def __len__(self) -> int:
        return len(self._vessels)

    def vessels(self) -> list[VesselState]:
        return list(self._vessels.values())

    def get(self, mmsi: int) -> VesselState | None:
        return self._vessels.get(mmsi)

    def apply_static(self, update: dict[str, Any]) -> VesselState:
        mmsi = int(update["mmsi"])
        state = self._vessels.setdefault(mmsi, VesselState(mmsi=mmsi))
        if update.get("name"):
            state.name = update["name"]
        if update.get("ship_type"):
            state.ship_type = update["ship_type"]
        if update.get("flag"):
            state.flag = update["flag"]
        if update.get("country"):
            state.country = update["country"]
        return state

    def apply_position(
        self,
        update: dict[str, Any],
        *,
        ingest_at: datetime | None = None,
        gap_monitor: bool | None = None,
    ) -> VesselState:
        mmsi = int(update["mmsi"])
        state = self._vessels.setdefault(mmsi, VesselState(mmsi=mmsi))
        if gap_monitor is not None:
            state.gap_monitor = gap_monitor
        if update.get("name"):
            state.name = update["name"]
        if update.get("ship_type"):
            state.ship_type = update["ship_type"]
        if update.get("flag"):
            state.flag = update["flag"]
        if update.get("country"):
            state.country = update["country"]
        if update.get("nav_status"):
            state.nav_status = update["nav_status"]

        point = PositionPoint(
            t=update["t"],
            lat=float(update["lat"]),
            lon=float(update["lon"]),
            sog=update.get("sog"),
            cog=update.get("cog"),
            heading=update.get("heading"),
        )
        state.latest = point
        state.track.append(point)
        if ingest_at is not None:
            state.last_ingest_at = ingest_at
        self._prune_track(state)
        return state

    def _prune_track(self, state: VesselState) -> None:
        if not state.track:
            return
        latest_t = state.track[-1].t
        cutoff = latest_t - self._track_max_age
        while state.track and state.track[0].t < cutoff:
            state.track.popleft()

    def snapshot(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for state in sorted(self._vessels.values(), key=lambda s: s.mmsi):
            if state.latest is None:
                continue
            events.append(self._to_ais_event(state))
        return events

    def tracks(self, *, min_points: int = 2) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for state in self._vessels.values():
            if len(state.track) < min_points:
                continue
            path = [[p.lon, p.lat] for p in state.track]
            out.append({"mmsi": state.mmsi, "path": path})
        return out

    def track_excerpt(self, mmsi: int) -> list[dict[str, Any]]:
        state = self._vessels.get(mmsi)
        if state is None:
            return []
        return [
            {
                "t": p.t.astimezone(timezone.utc).isoformat(),
                "lat": p.lat,
                "lon": p.lon,
                "sog": p.sog,
                "cog": p.cog,
            }
            for p in state.track
        ]

    def vessel_ais_event(self, state: VesselState) -> dict[str, Any]:
        return self._to_ais_event(state)

    def _to_ais_event(self, state: VesselState) -> dict[str, Any]:
        assert state.latest is not None
        p = state.latest
        return {
            "type": "ais",
            "mmsi": state.mmsi,
            "t": p.t.astimezone(timezone.utc).isoformat(),
            "lat": p.lat,
            "lon": p.lon,
            "sog": p.sog,
            "cog": p.cog,
            "heading": p.heading,
            "name": state.name,
            "ship_type": state.ship_type,
            "flag": state.flag,
            "country": state.country,
        }
