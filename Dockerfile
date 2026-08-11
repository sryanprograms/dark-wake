# syntax=docker/dockerfile:1

# ---- Stage 1: build the React/Vite frontend ----
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend (serves API + built frontend) ----
FROM python:3.11-slim AS backend
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir -e .

COPY backend/start.sh ./start.sh
RUN chmod +x ./start.sh

# Built SPA served by FastAPI at the same origin as the API.
COPY --from=frontend /frontend/dist ./app/static

EXPOSE 8000
CMD ["./start.sh"]
