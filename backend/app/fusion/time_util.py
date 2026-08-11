"""Shared datetime helpers for fusion."""

from __future__ import annotations

from datetime import datetime, timezone


def ensure_utc(t: datetime) -> datetime:
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)
