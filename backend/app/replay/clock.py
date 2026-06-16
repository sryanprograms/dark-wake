"""Replay clock with injectable position source (testable without real time)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable


def parse_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


PositionSource = Callable[[datetime, datetime], list[dict[str, Any]]]


@dataclass
class ReplayClock:
    start: datetime
    end: datetime
    position_source: PositionSource
    current: datetime | None = None
    playing: bool = False
    speed: float = 1.0
    _listeners: list[Callable[[dict[str, Any]], None]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.start = parse_time(self.start)
        self.end = parse_time(self.end)
        self.current = self.current or self.start

    def on_event(self, listener: Callable[[dict[str, Any]], None]) -> None:
        self._listeners.append(listener)

    def play(self) -> None:
        self.playing = True

    def pause(self) -> None:
        self.playing = False

    def seek(self, t: str | datetime) -> None:
        target = parse_time(t)
        if target < self.start:
            target = self.start
        if target > self.end:
            target = self.end
        self.current = target

    def set_speed(self, multiplier: float) -> None:
        self.speed = max(0.1, float(multiplier))

    def tick(self, wall_delta: timedelta) -> list[dict[str, Any]]:
        """Advance replay time and emit AIS events for the elapsed window."""
        if not self.playing or self.current is None:
            return []

        sim_delta = timedelta(seconds=wall_delta.total_seconds() * self.speed)
        window_start = self.current
        window_end = min(self.end, window_start + sim_delta)
        events = self.position_source(window_start, window_end)
        self.current = window_end
        if self.current >= self.end:
            self.playing = False
        for event in events:
            for listener in self._listeners:
                listener(event)
        return events


def in_memory_source(positions: Iterable[dict[str, Any]]) -> PositionSource:
    """Build a position source from a sorted or unsorted fixture list."""
    parsed = [
        {**pos, "_t": parse_time(pos["t"])}
        for pos in positions
    ]

    def source(start: datetime, end: datetime) -> list[dict[str, Any]]:
        out = []
        for pos in parsed:
            if start <= pos["_t"] < end:
                out.append({k: v for k, v in pos.items() if k != "_t"})
        return out

    return source
