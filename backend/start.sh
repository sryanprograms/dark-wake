#!/usr/bin/env sh
set -e

# Apply pending SQL migrations (idempotent; also enables the PostGIS extension).
python -m app.db.migrate

# Render (and most PaaS) inject the listen port via $PORT.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
