"""Environment-backed settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Repo root `.env` (start_backend.sh cd's into backend/)
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ROOT_ENV, override=True)
load_dotenv(_BACKEND_ENV, override=True)


@dataclass(frozen=True)
class Settings:
    database_url: str
    gfw_api_token: str
    aisstream_api_key: str
    digitraffic_user: str
    live_track_buffer_hours: float
    sar_poll_interval_s: int
    ais_persist_enabled: bool
    ais_persist_flush_interval_s: int
    ais_persist_min_interval_s: int


def _env(name: str, default: str = "") -> str:
    """Read env var and strip whitespace/quotes that dashboards sometimes add."""
    raw = os.getenv(name, default)
    if raw is None:
        return default
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=_env(
            "DATABASE_URL",
            "postgresql://darkwake:darkwake@localhost:5432/darkwake",
        ),
        gfw_api_token=_env("GFW_API_TOKEN"),
        aisstream_api_key=_env("AISSTREAM_API_KEY"),
        digitraffic_user=_env(
            "DIGITRAFFIC_USER",
            "DarkWake/Phase0Spike 0.1 (contact: dev@localhost)",
        ),
        live_track_buffer_hours=float(_env("LIVE_TRACK_BUFFER_HOURS", "6")),
        sar_poll_interval_s=int(_env("SAR_POLL_INTERVAL_S", "3600")),
        ais_persist_enabled=_env("AIS_PERSIST_ENABLED", "true").lower()
        in ("1", "true", "yes"),
        ais_persist_flush_interval_s=int(_env("AIS_PERSIST_FLUSH_INTERVAL_S", "15")),
        ais_persist_min_interval_s=int(_env("AIS_PERSIST_MIN_INTERVAL_S", "60")),
    )
