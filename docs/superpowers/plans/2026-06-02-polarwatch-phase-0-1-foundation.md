# DarkWake Phase 0–1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Spec:** `docs/superpowers/specs/darkwake-design.md` (v4) is the source of truth. This plan covers **Phase 0 (Overlap spike)** and **Phase 1 (Visualization)** only. Do not start Phase 2 (gap detection / prediction) until both phases here meet their definition of done.

**Goal:** Prove AIS-and-SAR temporal overlap for a chosen AOI (Phase 0), then stand up a replayable AIS visualization over that AOI on a map (Phase 1). No fusion, no dark-contact matching, no behavioral rules yet.

**Architecture:** Monorepo per spec §12 — `backend/app/` (FastAPI + PostGIS ingest/replay/API), `frontend/` (React + Vite + deck.gl + MapLibre), and `scripts/` (overlap spike + data pulls). PostgreSQL/PostGIS is the store from day one; geometry in WGS84 (EPSG:4326), distance in `geography`/metric CRS — never degrees. The AOI bbox and all thresholds live in config modules, not inline.

**Tech stack:** Python 3.11+, FastAPI + uvicorn, asyncpg or SQLAlchemy 2.x, GeoPandas + Shapely, httpx/websockets (AIS + GFW), pytest. Frontend: React + Vite + TypeScript, deck.gl over MapLibre GL JS. Docker Compose: PostGIS + backend (+ frontend dev server or static build).

**Key design decisions (locked):**

- **AOI is config, not code.** Default demo AOI: Gulf of Finland cable corridor (`config/aoi.py`), roughly 59.3–60.3°N, 23.5–27.0°E. Hormuz is an alternate; do not hard-code either outside config.
- **Phase 0 is the gate.** If AIS and SAR do not overlap spatially and temporally for the chosen bbox/window, change the date or bbox before building Phase 1.
- **AIS source follows the overlap path.** Historical replay: Danish Maritime Authority daily CSV (western Baltic, guaranteed history) or Fintraffic for Gulf of Finland. Flexible live path: AISStream.io WebSocket (record a window to DB). Pick whichever gives overlap with GFW SAR for the chosen window.
- **SAR source is GFW REST** (`ingest/sar_gfw.py` / `scripts/pull_sar.py`). Pull detections yourself; do not use GFW's precomputed matched/unmatched flag.
- **Phase 1 scope is AIS-only on the map.** SAR layer, connector lines, dark contacts, and behavioral flags are Phase 3+.
- **No ML, no custom SAR detector, no spoofing detection** in Phase 0–1 (spec §3 non-goals).
- **Runtime data is gitignored** — everything under `data/` and recorded AIS captures.

**Note on existing scaffold:** The repo currently has a `src/polarwatch/` package skeleton from an earlier PolarWatch plan. Replace/restructure toward the DarkWake layout in Task 1; do not extend the old BarentsWatch/Parquet pipeline.

---

## File structure (target after Phase 0–1)

| File | Responsibility |
|---|---|
| `docker-compose.yml` | PostGIS + backend (+ optional frontend service) |
| `README.md` | Project intro, Phase 0 gate instructions, Phase 1 quickstart |
| `.env.example` | `DATABASE_URL`, `GFW_API_TOKEN`, `AISSTREAM_API_KEY`, optional Fintraffic keys |
| `backend/pyproject.toml` | Backend deps, console scripts |
| `backend/app/main.py` | FastAPI app entry |
| `backend/app/config/aoi.py` | Bounding box + scenario metadata |
| `backend/app/config/settings.py` | Env-backed settings |
| `backend/app/config/thresholds.py` | Tunable defaults (stub in Phase 0–1; used from Phase 2+) |
| `backend/app/db/models.py` | SQLAlchemy/async models matching spec §7 (Phase 1: `vessel`, `ais_position`) |
| `backend/app/db/migrations/` | Initial schema migration |
| `backend/app/ingest/ais_csv.py` | Load DMA (or similar) CSV → PostGIS |
| `backend/app/ingest/ais_stream.py` | AISStream WebSocket recorder (optional path) |
| `backend/app/ingest/sar_gfw.py` | GFW SAR detection fetch (Phase 0 spike + later fusion) |
| `backend/app/replay/clock.py` | Replay clock with injectable time source (testable) |
| `backend/app/replay/streamer.py` | Push `ais` events over WebSocket during replay |
| `backend/app/api/ws.py` | `/ws/replay` — play/pause/seek/speed |
| `backend/app/api/rest.py` | `GET /scenarios`, `GET /vessels/{mmsi}/track` (Phase 1 minimum) |
| `frontend/` | Vite + React + deck.gl map + replay controls |
| `scripts/spike_overlap.py` | Phase 0 gate: confirm AIS + SAR overlap for AOI/window |
| `scripts/pull_sar.py` | Pull GFW SAR detections for AOI/date to `data/` |
| `backend/tests/` | pytest modules per component |

---

## Phase 0 — Overlap spike (the gate)

**Done when:** For one chosen moment inside the AOI/window, you can show a set of AIS positions and a set of GFW SAR detections over the same water — spatially and temporally aligned. Document the chosen bbox, date range, AIS source, and SAR scene timestamp in the spike output.

### Task 1: Repo restructure + config skeleton

**Files:**
- Create/restructure: `backend/app/config/{aoi,settings,thresholds}.py`, update `.env.example`, `.gitignore`, `README.md` (skeleton)
- Remove or archive: `src/polarwatch/` (superseded)

- [ ] **Step 1: Restructure toward spec §12 layout**

Create `backend/app/`, `frontend/`, `scripts/` directories. Move or replace the old `polarwatch` package; backend code lives under `backend/app/`.

- [ ] **Step 2: Create `backend/app/config/aoi.py`**

```python
# Gulf of Finland cable corridor (primary demo AOI)
AOI_NAME = "gulf_of_finland"
BBOX = {
    "min_lat": 59.3,
    "max_lat": 60.3,
    "min_lon": 23.5,
    "max_lon": 27.0,
}
# Default scenario window — adjust after spike if overlap fails
DEFAULT_START = "2024-10-08T00:00:00Z"
DEFAULT_END   = "2024-10-09T00:00:00Z"
```

- [ ] **Step 3: Create `backend/app/config/settings.py`**

Load from env: `DATABASE_URL`, `GFW_API_TOKEN`, `AISSTREAM_API_KEY`. Sensible defaults for local dev.

- [ ] **Step 4: Create stub `backend/app/config/thresholds.py`**

Copy fusion/behavior threshold constants from spec §8 and §9 as documented defaults. Not used in Phase 0–1 logic yet; prevents magic numbers later.

- [ ] **Step 5: Update `.env.example`**

```
DATABASE_URL=postgresql://darkwake:darkwake@localhost:5432/darkwake
GFW_API_TOKEN=
AISSTREAM_API_KEY=
```

- [ ] **Step 6: Update `.gitignore`**

Ensure `data/`, `.env`, `node_modules/`, `frontend/dist/`, Python caches, and venvs are ignored.

- [ ] **Step 7: Commit**

```bash
git add backend/app/config/ .env.example .gitignore README.md
git commit -m "chore: restructure repo for DarkWake Phase 0 config"
```

---

### Task 2: GFW SAR pull script

**Files:**
- Create: `backend/app/ingest/sar_gfw.py`, `scripts/pull_sar.py`
- Test: `backend/tests/test_sar_gfw.py` (mock httpx; no live network in CI)

- [ ] **Step 1: Write failing tests for GFW client**

Test that `fetch_detections(bbox, start, end, client)` parses GFW REST JSON into `{t, lat, lon, length_m, scene_id, confidence}` records. Use `httpx.MockTransport`.

- [ ] **Step 2: Implement `sar_gfw.py`**

Call GFW vessel-detection REST API with bearer token. Filter to bbox. Return normalized detection dicts.

- [ ] **Step 3: Implement `scripts/pull_sar.py`**

CLI: read AOI + date window from config/env, call `fetch_detections`, write `data/sar_{aoi}_{date}.json` (or GeoJSON).

- [ ] **Step 4: Run tests**

Run: `pytest backend/tests/test_sar_gfw.py -v`
Expected: all pass offline.

- [ ] **Step 5: Manual pull (requires `GFW_API_TOKEN`)**

Run: `python scripts/pull_sar.py --start 2024-10-08 --end 2024-10-09`
Expected: non-empty detection file for the Gulf of Finland window (adjust dates if empty).

- [ ] **Step 6: Commit**

```bash
git add backend/app/ingest/sar_gfw.py scripts/pull_sar.py backend/tests/test_sar_gfw.py
git commit -m "feat: add GFW SAR detection pull client"
```

---

### Task 3: AIS sample pull (historical path)

**Files:**
- Create: `backend/app/ingest/ais_csv.py`, `scripts/pull_ais.py` (or equivalent)
- Test: `backend/tests/test_ais_csv.py`

For Phase 0, prefer **Danish Maritime Authority daily CSV** or **Fintraffic** — whichever covers the AOI with guaranteed historical data. DMA is western Baltic; confirm it reaches the Gulf of Finland bbox or switch to Fintraffic/AISStream recording.

- [ ] **Step 1: Choose AIS source for the default AOI**

Document the choice in `README.md`. If DMA CSV does not cover the bbox, use Fintraffic API or record an AISStream window.

- [ ] **Step 2: Write failing tests for CSV normalization**

Test that a sample DMA/Fintraffic row maps to `{mmsi, t, lat, lon, sog, cog, heading, name}`.

- [ ] **Step 3: Implement `ais_csv.py`**

Parse source CSV/API response, filter to AOI bbox and time window, return normalized position records.

- [ ] **Step 4: Implement pull script**

Write filtered positions to `data/ais_{aoi}_{date}.json` (or CSV).

- [ ] **Step 5: Manual pull**

Run pull for the same window as Task 2 SAR pull.
Expected: non-empty AIS file with positions inside the bbox.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ingest/ais_csv.py scripts/ backend/tests/test_ais_csv.py README.md
git commit -m "feat: add AIS historical pull for overlap spike"
```

---

### Task 4: Overlap spike script (Phase 0 done-criterion)

**Files:**
- Create: `scripts/spike_overlap.py`
- Test: `backend/tests/test_spike_overlap.py`

- [ ] **Step 1: Write failing tests**

Synthetic fixtures: AIS positions spanning 08:00–20:00 UTC; SAR detections at 14:30 UTC inside bbox. Assert spike reports `overlap: true` and names the SAR scene time. Negative fixture: SAR scene outside AIS window → `overlap: false`.

- [ ] **Step 2: Implement overlap logic**

Load AIS + SAR files from `data/`. Check:
1. At least one SAR detection centroid falls inside the AOI bbox.
2. AIS coverage window brackets at least one SAR scene timestamp (± configurable margin, e.g. 1 h).
3. At that timestamp, at least N AIS positions exist inside the bbox (configurable minimum).

Print a human-readable report: bbox, AIS source, AIS time range, SAR scene times, counts, pass/fail.

- [ ] **Step 3: Run against real pulled data**

Run: `python scripts/spike_overlap.py --ais data/ais_*.json --sar data/sar_*.json`
Expected: **PASS**. If fail, adjust date/bbox per spec §4 and re-pull before proceeding.

- [ ] **Step 4: Commit**

```bash
git add scripts/spike_overlap.py backend/tests/test_spike_overlap.py
git commit -m "feat: add Phase 0 AIS-SAR overlap spike gate"
```

**Phase 0 checkpoint:** Do not start Phase 1 until the spike passes on real data for the chosen scenario.

---

## Phase 1 — Visualization (AIS on a map, replayable)

**Done when:** `docker compose up` boots PostGIS + backend; loading the Phase 0 AIS window into the DB and opening the frontend lets you play/scrub the replay and watch real vessels move over the AOI. No SAR layer yet.

### Task 5: Docker + PostGIS + schema

**Files:**
- Create: `docker-compose.yml`, `backend/Dockerfile`, `backend/app/db/models.py`, `backend/app/db/migrations/001_initial.sql`

- [ ] **Step 1: Create `docker-compose.yml`**

Services: `postgis` (PostGIS 16), `backend` (FastAPI, depends on postgis). No Redis (not in DarkWake spec). Expose 5432 and backend port (8000).

- [ ] **Step 2: Create initial migration matching spec §7 (Phase 1 subset)**

Tables: `vessel`, `ais_position` with `geom GEOMETRY(Point,4326)`, indexes on `(mmsi, t)` and GIST on `geom`. Defer `sar_detection`, `contact`, `asset`, `behavior_event` to later phases (or create empty stubs if easier — they stay unused in Phase 1).

- [ ] **Step 3: Wire SQLAlchemy/asyncpg models**

`AisPosition` row ↔ spec columns. Helper to insert positions from normalized ingest records.

- [ ] **Step 4: Verify stack boots**

Run: `docker compose up --build`
Expected: PostGIS healthy, backend starts, migration applied.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml backend/Dockerfile backend/app/db/
git commit -m "feat: add PostGIS stack and AIS schema"
```

---

### Task 6: AIS loader → database

**Files:**
- Extend: `backend/app/ingest/ais_csv.py` (or add `loader.py`)
- Create: CLI command or script `scripts/load_ais.py`
- Test: `backend/tests/test_ais_loader.py` (use test DB or transactional fixture)

- [ ] **Step 1: Write failing tests**

Load a small fixture CSV/JSON into DB; query back count and sample geometry; assert WGS84 point stored correctly.

- [ ] **Step 2: Implement loader**

Bulk insert positions; upsert `vessel` rows from latest known name/type fields.

- [ ] **Step 3: Load Phase 0 AIS data**

Run loader against the file that passed the overlap spike.
Expected: row count matches spike AIS count.

- [ ] **Step 4: Commit**

```bash
git add backend/app/ingest/ backend/tests/test_ais_loader.py scripts/load_ais.py
git commit -m "feat: load AIS positions into PostGIS"
```

---

### Task 7: Replay clock + WebSocket streamer

**Files:**
- Create: `backend/app/replay/clock.py`, `backend/app/replay/streamer.py`, `backend/app/api/ws.py`
- Test: `backend/tests/test_replay_clock.py`, `backend/tests/test_ws_replay.py`

- [ ] **Step 1: Write failing tests for replay clock**

Injectable clock; `seek(t)`, `play()`, `pause()`, `speed multiplier`. Emit ordered AIS events from DB for `[t, t+Δ]`. Tests run without real time delays.

- [ ] **Step 2: Implement `clock.py`**

Query `ais_position` rows in time order for the loaded scenario window.

- [ ] **Step 3: Write failing WebSocket tests**

Client sends `{action: "play"|"pause"|"seek", ...}`; server pushes `{type: "ais", mmsi, t, lat, lon, sog, cog, heading}` events. Use FastAPI `TestClient` + websockets test helper.

- [ ] **Step 4: Implement `/ws/replay`**

Wire clock to streamer; support play/pause/seek/speed per spec §10.

- [ ] **Step 5: Commit**

```bash
git add backend/app/replay/ backend/app/api/ws.py backend/tests/
git commit -m "feat: add replay clock and AIS WebSocket stream"
```

---

### Task 8: REST API (Phase 1 minimum)

**Files:**
- Create: `backend/app/api/rest.py`, `backend/app/main.py`
- Test: `backend/tests/test_rest.py`

- [ ] **Step 1: Implement endpoints**

- `GET /scenarios` — list loaded scenario(s) with time range and bbox
- `GET /vessels/{mmsi}/track?start=&end=` — positions for detail/highlight

- [ ] **Step 2: Tests for REST**

Assert JSON shapes and 404 for unknown MMSI.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/rest.py backend/app/main.py backend/tests/test_rest.py
git commit -m "feat: add Phase 1 REST endpoints"
```

---

### Task 9: Frontend — map + replay controls

**Files:**
- Create: `frontend/` (Vite + React + TS), `frontend/src/map/`, `frontend/src/ws/`, `frontend/src/components/ReplayControls.tsx`

- [ ] **Step 1: Scaffold frontend**

`npm create vite@latest frontend -- --template react-ts`. Add deck.gl, `@deck.gl/layers`, `@deck.gl/mapbox`, `maplibre-gl`.

- [ ] **Step 2: Dark basemap**

MapLibre with CARTO dark / OpenFreeMap / Protomaps (no token lock-in).

- [ ] **Step 3: AIS layer**

`ScatterplotLayer` or `IconLayer` for vessels; oriented by heading; muted color per spec §11 (AIS-only phase — no SAR/dark styling yet).

- [ ] **Step 4: WebSocket client**

Connect to `/ws/replay`; update vessel positions on `ais` events; maintain latest position per MMSI.

- [ ] **Step 5: Replay controls**

Play, pause, speed, scrub bar bound to scenario time range. Send control messages to WebSocket.

- [ ] **Step 6: Wire docker-compose frontend service (optional)**

Either serve frontend via Vite dev server in compose, or build static assets and mount in backend.

- [ ] **Step 7: Manual verification (Phase 1 done-criterion)**

1. `docker compose up`
2. Load AIS data for the Phase 0 scenario
3. Open map UI, press play
4. Observe vessels moving over the Gulf of Finland AOI

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: add AIS map visualization with replay controls"
```

---

### Task 10: README + end-to-end documentation

**Files:**
- Update: `README.md`

- [ ] **Step 1: Document Phase 0 gate**

How to set tokens, pull AIS + SAR, run `spike_overlap.py`, and what PASS means.

- [ ] **Step 2: Document Phase 1 quickstart**

```bash
docker compose up --build
python scripts/load_ais.py ...
# open http://localhost:5173 (or documented URL)
```

- [ ] **Step 3: Document chosen scenario**

Record the bbox, date window, AIS source, and SAR scene time that passed the spike.

- [ ] **Step 4: Architecture diagram (ASCII or mermaid)**

```
AIS file/DB ──► replay clock ──► WebSocket ──► deck.gl map
                     ▲
              replay controls
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add DarkWake Phase 0–1 README and quickstart"
```

---

## Self-review notes

**Spec coverage (Phase 0–1 only):**

| Spec § | Requirement | Plan task |
|---|---|---|
| §4 | AOI is config; confirm overlap before building | Tasks 1, 4 |
| §5 | GFW SAR + AIS source (DMA/Fintraffic/AISStream) | Tasks 2, 3 |
| §6 | PostGIS, FastAPI, GeoPandas/Shapely, deck.gl + MapLibre | Tasks 5–9 |
| §7 | `vessel`, `ais_position` schema | Task 5 |
| §10 | `/ws/replay` with play/pause/seek/speed; minimal REST | Tasks 7, 8 |
| §11 | AIS vessels on dark basemap; replay controls | Task 9 |
| §13 Phase 0 | Overlap spike done-criterion | Task 4 |
| §13 Phase 1 | AIS on map, replayable, no fusion | Tasks 5–9 |
| §14 | Thresholds in config; geometry discipline; one phase at a time | Tasks 1, 5 |

**Intentionally deferred (Phase 2+ per spec §13):**

- Gap detection and dead-reckoning (`detection/gaps.py`, `fusion/predict.py`) — Phase 2
- SAR fusion, matcher, dark contacts, connector lines — Phase 3
- Re-identification, suspicion score, asset layer — Phase 4
- Behavioral rules (`detection/behavior.py`) — Phase 5
- Spoofing, custom SAR detector, live mode — Phase 6 optional flexes

**Migration note:** Existing `src/polarwatch/model.py` and `tests/test_model.py` are from the superseded PolarWatch plan. They are not part of the DarkWake data model (PostGIS geometry, not Pydantic-only Parquet). Remove or replace during Task 1 restructure.

**Open verification items:**

- Confirm DMA CSV geographic coverage reaches the Gulf of Finland bbox; switch to Fintraffic or AISStream if not.
- Confirm GFW REST endpoint and auth against current GFW docs before relying on live pulls.
- Tune default scenario dates after first successful overlap spike; document the working window in README.
