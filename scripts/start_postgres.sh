#!/usr/bin/env bash
# Start Homebrew PostgreSQL (brew services with pg_ctl fallback).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/pg_version.sh"

PG_PREFIX="$(brew --prefix postgresql@${DARKWAKE_PG_VERSION})"
PG_BIN="$PG_PREFIX/bin"
PG_DATA="/opt/homebrew/var/postgresql@${DARKWAKE_PG_VERSION}"
PG_SHARE="$("$PG_BIN/pg_config" --sharedir)"
POSTGIS_CONTROL="$PG_SHARE/extension/postgis.control"

if [[ ! -f "$POSTGIS_CONTROL" ]]; then
  # Fallback: postgis keg layout
  POSTGIS_CONTROL="$(brew --prefix postgis)/share/postgresql@${DARKWAKE_PG_VERSION}/extension/postgis.control"
fi

if [[ ! -f "$POSTGIS_CONTROL" ]]; then
  echo "ERROR: PostGIS extension not found for postgresql@${DARKWAKE_PG_VERSION}." >&2
  echo "       Expected at: $PG_SHARE/extension/postgis.control" >&2
  echo "       Run: brew reinstall postgis" >&2
  exit 1
fi

export PATH="$PG_BIN:$PATH"

if pg_isready -h localhost -q 2>/dev/null; then
  RUNNING_VERSION="$("$PG_BIN/psql" -h localhost -tAc 'SHOW server_version_num;' 2>/dev/null || true)"
  if [[ -n "$RUNNING_VERSION" && "$RUNNING_VERSION" -ge 170000 ]]; then
    echo "PostgreSQL ${DARKWAKE_PG_VERSION} already running."
    exit 0
  fi
  echo "Stopping older PostgreSQL on port 5432 (server_version_num=${RUNNING_VERSION:-unknown})..."
  brew services stop postgresql@16 2>/dev/null || true
  brew services stop postgresql@18 2>/dev/null || true
  for ver in 16 18; do
    OLD_DATA="/opt/homebrew/var/postgresql@${ver}"
    if [[ -d "$OLD_DATA" ]] && [[ -x "$(brew --prefix postgresql@${ver} 2>/dev/null)/bin/pg_ctl" ]]; then
      "$(brew --prefix postgresql@${ver})/bin/pg_ctl" -D "$OLD_DATA" stop -m fast 2>/dev/null || true
    fi
  done
  sleep 2
fi

echo "Starting PostgreSQL ${DARKWAKE_PG_VERSION}..."
if brew services start "postgresql@${DARKWAKE_PG_VERSION}" 2>/dev/null; then
  for _ in {1..15}; do
    if pg_isready -h localhost -q 2>/dev/null; then
      echo "PostgreSQL started via brew services."
      exit 0
    fi
    sleep 1
  done
fi

echo "brew services failed — trying pg_ctl..."
LOG_FILE="${TMPDIR:-/tmp}/darkwake-postgresql@${DARKWAKE_PG_VERSION}.log"
LC_ALL=en_US.UTF-8 "$PG_BIN/pg_ctl" -D "$PG_DATA" -l "$LOG_FILE" start

for _ in {1..15}; do
  if pg_isready -h localhost -q 2>/dev/null; then
    echo "PostgreSQL started via pg_ctl (log: $LOG_FILE)."
    exit 0
  fi
  sleep 1
done

echo "ERROR: PostgreSQL did not become ready. Check $LOG_FILE" >&2
exit 1
