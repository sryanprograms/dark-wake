# DarkWake — Project Overview

## What it is (2-sentence summary)

DarkWake is a maritime domain-awareness tool that detects "dark ships" — vessels that
go dark by switching off their AIS transponders — by fusing live and historical AIS
position data with satellite SAR (synthetic-aperture radar) vessel detections over a
defined area of interest. When a radar contact appears where no broadcasting vessel
should be, or a tracked ship falls silent near sensitive infrastructure, DarkWake
surfaces it on a live/replayable map as a tiered operator alert.

---

## Problem

Vessels are legally required to broadcast AIS (Automatic Identification System) position
reports. Bad actors disable AIS — "going dark" — to hide activity such as sanctions
evasion, illegal fishing, or interference with subsea cables and other critical
infrastructure. AIS alone can't see these ships; satellite SAR can image any vessel
regardless of its transponder, but produces sparse, unattributed radar blobs. The signal
lives in the *fusion* of the two feeds.

## Approach

DarkWake correlates two independent data sources within an area of interest (AOI):

1. **AIS** — vessel self-reported positions (live via AISStream / Digitraffic; historical
   via the Danish Maritime Authority).
2. **SAR** — satellite radar vessel detections (via Global Fishing Watch / GFW).

The core idea: every SAR detection should match a known AIS track in space and time. A
SAR contact with **no** corresponding AIS report is a candidate dark ship. The system
also watches for behavioral precursors — AIS silence gaps, loitering, and "dragging"
tracks near subsea cables — and raises tiered alerts (`watch` → `suspicious`), explicitly
labeled as precursors rather than confirmed verdicts.

## Primary demo AOI

Southern Baltic / **Danish Belt** (`min_lat 54.8, max_lat 56.8, min_lon 10.2, max_lon 13.2`),
chosen for reliable GFW SAR coverage and good historical AIS overlap. The AOI bbox is a
configuration parameter, not hard-coded logic.

---

## Architecture

```
AIS feeds (AISStream / Digitraffic / DMA history)  ┐
                                                     ├─►  Ingest ─► PostGIS ─► Fusion ─► API (REST + WS) ─► React map UI
SAR detections (Global Fishing Watch)              ┘
```

### Backend — `backend/` (Python 3.11, FastAPI)
- **`app/main.py`** — FastAPI app. REST routers plus three WebSocket channels:
  `/ws/timeline`, `/ws/replay`, `/ws/live`.
- **`app/ingest/`** — AIS ingest service.
- **`app/live/`** — live mode: vessel registry, AIS-gap/silence detection (`detect.py`),
  SAR polling (`sar_poller.py`), PostGIS persistence, the live hub.
- **`app/fusion/`** — AIS↔SAR matching, dead-reckoning prediction, scene clustering.
- **`app/replay/` + `app/timeline/`** — historical replay and timeline scrubbing
  (30-day history window, window presets 24h / 3d / 7d).
- **`app/spike_overlap.py`** — Phase 0 overlap gate: proves AIS and SAR data actually
  overlap in the AOI/time window before deeper work (PASS/FAIL report).
- **`app/config/`** — `aoi.py` (bbox + GFW query polygon), `thresholds.py` (all tunable
  fusion/behavioral/replay constants), `settings.py`.
- **`app/db/`** — PostGIS schema + migrations.
- REST endpoints: `/health`, `/assets/cables`, `/scenarios`, `/vessels/{mmsi}/track`, `/events`.

### Frontend — `frontend/` (React + TypeScript + Vite)
- **`src/App.tsx`** — main app, corridor/timeline state, WebSocket wiring.
- **`src/map/MapView.tsx`** — vessel + track map rendering.
- **Components** — `TimelineDock`, `FleetPanel`, `EventFeed`, `SceneContactFeed`,
  `VesselDetail`, `LayerToggles`, `NationFilter`, `ShipTypeFilter`, `MapLegend`, `TopBar`.
- **`src/ws/`** — `live`, `replay`, `timeline` WebSocket clients.

### Infrastructure
- **`docker-compose.yml`** — PostGIS 16/3.4 + backend (auto-migrate + uvicorn `--reload`).
- **`scripts/`** — data pulls (`pull_ais.py`, `pull_sar.py`), loaders
  (`load_live_ais.py`, `load_sar.py`), local setup, and `run_phase0_gate.py`.

---

## Key detection thresholds (`backend/app/config/thresholds.py`)

| Concept | Value | Meaning |
|---|---|---|
| SAR match radius | 750 m | max distance to call an AIS track and SAR blob the same vessel |
| SAR match time window | 600 s | max time offset for that match |
| AIS gap (min / high) | 30 min / 60 min | silence before a `watch` / `suspicious` alert |
| Loiter | ≤ 3 kn for ≥ 30 min | low-speed dwell near assets |
| Drag | 0.5–5 kn over ≥ 10 km | cable-drag behavioral signature |
| Asset proximity | 2000 m | "near critical infrastructure" radius |

---

## Status / phasing

- **Phase 0 (done)** — AIS/SAR overlap spike + data-pull pipeline (overlap gate).
- **Phase 1 (done)** — AIS replay map on the PostGIS stack.
- **Live-first mode (latest)** — AISStream live ingest, SAR polling, operator alerts, map UI.

(History: the project was originally scaffolded as "PolarWatch" before becoming DarkWake.)

## Data sources & credentials

Configured via `.env` (see `.env.example`):
- `GFW_API_TOKEN` — Global Fishing Watch (SAR).
- `AISSTREAM_API_KEY` — live AIS stream.
- `DIGITRAFFIC_USER` — Digitraffic AIS metadata.
- `DATABASE_URL` — PostGIS connection.
- `AIS_PERSIST_*` — toggles persisting live AIS to PostGIS for timeline replay / SAR fusion.

## Running locally

```bash
docker compose up            # PostGIS + backend (auto-migrate + uvicorn on :8000)
npm run install:frontend     # one-time
npm run dev                  # Vite frontend (:5173)
npm run load:live -- --clear # pull live AIS into the DB
```
