#!/usr/bin/env bash
# Finish DB setup after Homebrew postgres/postgis install (if setup_local.sh failed at service start).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

# shellcheck disable=SC1091
source "$ROOT/scripts/pg_version.sh"

bash "$ROOT/scripts/start_postgres.sh"

PG_BIN="$(brew --prefix postgresql@${DARKWAKE_PG_VERSION})/bin"
export PATH="$PG_BIN:$PATH"

psql postgres -v ON_ERROR_STOP=0 -tc "SELECT 1 FROM pg_roles WHERE rolname='darkwake'" | grep -q 1 \
  || psql postgres -c "CREATE USER darkwake WITH PASSWORD 'darkwake' CREATEDB;"

psql postgres -v ON_ERROR_STOP=0 -tc "SELECT 1 FROM pg_database WHERE datname='darkwake'" | grep -q 1 \
  || psql postgres -c "CREATE DATABASE darkwake OWNER darkwake;"

psql darkwake -c "CREATE EXTENSION IF NOT EXISTS postgis;"

cd "$ROOT/backend"
export DATABASE_URL="${DATABASE_URL:-postgresql://darkwake:darkwake@localhost:5432/darkwake}"
python -m app.db.migrate

echo "Database ready."
