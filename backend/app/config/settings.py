"""Environment-backed settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    gfw_api_token: str
    aisstream_api_key: str
    digitraffic_user: str


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
    )
