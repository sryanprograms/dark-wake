#!/usr/bin/env bash
# One-time local setup: Python venv, frontend deps, PostgreSQL+PostGIS (no Docker).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> DarkWake local setup"

# --- Python ---
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Creating Python venv..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
pip install -U pip -q
pip install -e ".[dev]" -e "./backend[dev]"

# --- Frontend ---
echo "Installing frontend dependencies..."
npm install --prefix frontend

# --- Environment ---
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — add GFW_API_TOKEN if pulling SAR."
fi

# --- Database (Homebrew when Docker is missing) ---
if command -v docker &>/dev/null; then
  echo "Docker found. Use: docker compose up --build"
  echo "Setup complete."
  exit 0
fi

echo "Docker not installed — setting up Homebrew PostgreSQL + PostGIS..."

# shellcheck disable=SC1091
source "$ROOT/scripts/pg_version.sh"

if ! command -v brew &>/dev/null; then
  echo "ERROR: Homebrew required. Install from https://brew.sh" >&2
  exit 1
fi

if ! brew list "postgresql@${DARKWAKE_PG_VERSION}" &>/dev/null; then
  echo "Installing postgresql@${DARKWAKE_PG_VERSION} and postgis (this may take a few minutes)..."
  echo "Note: Homebrew postgis only supports PostgreSQL 17/18 — we use @${DARKWAKE_PG_VERSION}."
  brew install "postgresql@${DARKWAKE_PG_VERSION}" postgis
fi

PG_BIN="$(brew --prefix postgresql@${DARKWAKE_PG_VERSION})/bin"
export PATH="$PG_BIN:$PATH"

bash "$ROOT/scripts/start_postgres.sh"

# Create role + database (idempotent)
psql postgres -v ON_ERROR_STOP=0 -tc "SELECT 1 FROM pg_roles WHERE rolname='darkwake'" | grep -q 1 \
  || psql postgres -c "CREATE USER darkwake WITH PASSWORD 'darkwake' CREATEDB;"

psql postgres -v ON_ERROR_STOP=0 -tc "SELECT 1 FROM pg_database WHERE datname='darkwake'" | grep -q 1 \
  || psql postgres -c "CREATE DATABASE darkwake OWNER darkwake;"

psql darkwake -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Run migrations (backend installed editable into venv)
cd "$ROOT/backend"
DATABASE_URL="${DATABASE_URL:-postgresql://darkwake:darkwake@localhost:5432/darkwake}"
export DATABASE_URL
python -m app.db.migrate

echo ""
echo "Setup complete."
echo ""
echo "Next steps:"
echo "  source .venv/bin/activate"
echo "  bash scripts/start_backend.sh          # terminal 1"
echo "  npm run dev                              # terminal 2 (from repo root)"
echo ""
echo "Optional — load AIS data:"
echo "  python scripts/pull_ais.py --source digitraffic --out data/ais_gulf_of_finland.json"
echo "  python scripts/load_ais.py data/ais_gulf_of_finland.json --clear"
