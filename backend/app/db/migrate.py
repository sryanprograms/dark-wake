"""Apply numbered SQL migrations from backend/app/db/migrations/."""

from __future__ import annotations

import os
import time
from pathlib import Path

import psycopg2

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _connect():
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://darkwake:darkwake@localhost:5432/darkwake",
    )
    last_err: Exception | None = None
    for _ in range(30):
        try:
            return psycopg2.connect(url)
        except psycopg2.OperationalError as exc:
            last_err = exc
            time.sleep(1)
    raise RuntimeError("could not connect to database") from last_err


def run() -> None:
    conn = _connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migration (
            name TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        cur.execute("SELECT 1 FROM schema_migration WHERE name = %s", (path.name,))
        if cur.fetchone():
            continue
        cur.execute(path.read_text())
        cur.execute("INSERT INTO schema_migration (name) VALUES (%s)", (path.name,))
        print(f"applied migration: {path.name}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    run()
