#!/usr/bin/env bash
# Start FastAPI backend (expects PostGIS running locally or in Docker).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

# Homebrew postgres on PATH when Docker isn't used
if ! command -v docker &>/dev/null && command -v brew &>/dev/null; then
  # shellcheck disable=SC1091
  source "$ROOT/scripts/pg_version.sh"
  bash "$ROOT/scripts/start_postgres.sh" || true
  PG_BIN="$(brew --prefix postgresql@${DARKWAKE_PG_VERSION} 2>/dev/null)/bin"
  if [[ -d "$PG_BIN" ]]; then
    export PATH="$PG_BIN:$PATH"
  fi
fi

export DATABASE_URL="${DATABASE_URL:-postgresql://darkwake:darkwake@localhost:5432/darkwake}"

echo "Applying migrations..."
cd "$ROOT/backend"
python -m app.db.migrate

echo "Starting backend on http://localhost:8000"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
