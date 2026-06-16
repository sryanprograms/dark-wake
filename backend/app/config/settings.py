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


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql://darkwake:darkwake@localhost:5432/darkwake",
        ),
        gfw_api_token=os.getenv("GFW_API_TOKEN", ""),
        aisstream_api_key=os.getenv("AISSTREAM_API_KEY", ""),
        digitraffic_user=os.getenv(
            "DIGITRAFFIC_USER",
            "DarkWake/Phase0Spike 0.1 (contact: dev@localhost)",
        ),
        live_track_buffer_hours=float(os.getenv("LIVE_TRACK_BUFFER_HOURS", "6")),
        sar_poll_interval_s=int(os.getenv("SAR_POLL_INTERVAL_S", "3600")),
    )
