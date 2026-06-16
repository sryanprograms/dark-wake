# AISStream Live Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Live-first AIS via AISStream with selective event persistence, SAR poller, and replay retained as secondary mode.

**Architecture:** Server-side AISStream consumer → in-memory `VesselRegistry` → `LiveHub` fans out to `/ws/live` clients. Gap detector persists to `operator_event`. GFW SAR poller broadcasts detections. Frontend defaults to live; replay via `?mode=replay`.

**Tech Stack:** Python 3.11, FastAPI, websockets, asyncio, PostGIS, React + Vite

**Spec:** `docs/superpowers/specs/2026-06-15-aisstream-live-design.md`

---

### Task 1: AISStream message parsing

**Files:**
- Create: `backend/app/ingest/ais_stream.py`
- Test: `backend/tests/test_ais_stream.py`

- [ ] Parse PositionReport + ShipStaticData into normalized dicts
- [ ] `aisstream_bounding_boxes(bbox)` helper in `aoi.py`
- [ ] Tests with fixture JSON from AISStream docs

### Task 2: In-memory vessel registry

**Files:**
- Create: `backend/app/live/registry.py`
- Test: `backend/tests/test_live_registry.py`

- [ ] Rolling track buffer with max age
- [ ] `snapshot()` and `tracks()` for WS broadcast

### Task 3: Gap detection + operator_event persistence

**Files:**
- Create: `backend/app/live/detect.py`, `backend/app/live/persist.py`
- Create: `backend/app/db/migrations/002_operator_event.sql`
- Modify: `backend/app/db/models.py`
- Test: `backend/tests/test_gap_detect.py`

### Task 4: LiveHub + AISStream consumer

**Files:**
- Create: `backend/app/live/hub.py`, `backend/app/live/__init__.py`
- Modify: `backend/pyproject.toml` (add websockets)

### Task 5: Live WebSocket + app lifespan

**Files:**
- Create: `backend/app/api/live_ws.py`
- Modify: `backend/app/main.py`, `backend/app/config/settings.py`

### Task 6: SAR poller

**Files:**
- Create: `backend/app/live/sar_poller.py`
- Wire into `LiveHub`

### Task 7: REST events endpoint

**Files:**
- Modify: `backend/app/api/rest.py`

### Task 8: Frontend live mode

**Files:**
- Create: `frontend/src/ws/live.ts`, `frontend/src/components/EventFeed.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/components/TopBar.tsx`, `frontend/src/types/layers.ts`, `frontend/src/map/MapView.tsx`

### Task 9: Verification

- [ ] `pytest backend/tests/ -q`
- [ ] `npm run build` in frontend
