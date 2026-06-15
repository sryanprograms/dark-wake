# Project DarkWake — Build Spec

A dark-ship detection system. DarkWake ingests two independent maritime data sources, compares them, and surfaces the vessels that one source sees and the other does not. The headline output is the dark ship: present in satellite radar, absent or false on AIS.

This document is the source of truth for an AI-agent-assisted build. Work one phase at a time, bottom-up.

---

## 1. The core idea

There are two ways to know where a ship is, and they fail in opposite directions:

- **AIS** is self-reported. A vessel broadcasts "I am here, I am this ship." It is rich and continuous, but it can be switched off (going dark) or faked (spoofing). You are trusting the ship to tell the truth.
- **SAR** (synthetic aperture radar, from satellites) is independent. A radar pass says "there is a metal object of roughly this size at this position at this instant," regardless of what the ship claims. It is sparse (a snapshot every few days) but it does not lie.

The signal is the gap between them. A radar return with no matching AIS broadcast is a vessel that does not want to be seen. That gap is the entire product. Everything DarkWake does is in service of computing it, visualizing it, and predicting from it.

One sentence: take in AIS and SAR, correlate them in space and time, and flag the vessels that appear in one but not the other.

## 2. The core loop

```
   AIS stream  ──►  positions over time (what ships claim)
                          │
                          ▼
       [ predict each vessel's position at SAR scene time ]
                          │
   SAR scene   ──►  radar detections (what is physically there)
                          │
                          ▼
        [ MATCH detections to predicted AIS positions ]
                          │
            ┌─────────────┼─────────────────────┐
            ▼             ▼                      ▼
      matched         SAR with no AIS       AIS with no SAR
   (normal vessel)   = DARK SHIP            = possible spoof / out of coverage
                       (headline output)

```

## 3. Scope and non-goals

In scope:

- Ingesting AIS and storing vessel tracks over time.
- Ingesting SAR vessel detections.
- The fusion: spatiotemporal correlation of the two, producing matched vs dark classifications.
- Prediction: dead-reckoning a vessel's position through an AIS gap, and using it to re-identify a dark radar contact.
- **Asset-anomaly behavioral detection (AIS-only):** flagging suspicious vessel behavior near a named asset such as an undersea cable (loitering, anchor-drag signature, slow crossing, type mismatch). A thin layer on the same pipeline. See Section 9.
- Visualization: a map that shows both data sources at once and makes the gap obvious.
- A suspicion score for dark contacts and behavioral flags.

Explicit non-goals (do not build unless a phase says so):

- No autonomous response or "action" simulation. That is a future slide.
- No dependence on a specific named incident. Dark contacts and anomalies occur constantly; the method does not need a famous event.
- No machine-learning model before the deterministic fusion and rules work. Both are deterministic geometry.
- No building a custom SAR detector until the detection-feed-based fusion works end to end (it is an optional later flex).

## 4. Location is a parameter, not a decision

The engine is location-agnostic. The area of interest is a bounding box in config. The same code runs anywhere AIS and SAR overlap. Two recommended demo targets:

- **Gulf of Finland cable corridor** (primary recommendation). The Finland-to-Estonia crossing, roughly 59.3 to 60.3 N and 23.5 to 27.0 E. Clean traffic, an active sabotage backdrop (Balticconnector 2023, Estlink 2 2024, Elisa cable 2025), good SAR coverage at high latitude, and undersea cables to draw as assets. This is the cleaner, faster demo, and it is where the asset-anomaly layer shines.
- **Strait of Hormuz** (high-impact alternate). The single most extreme dark-ship environment on Earth and the most directly US-relevant. The justification for the fusion lives here: a May 2026 SAR collection found roughly 97 vessels near the northern Hormuz corridor with only 3 transmitting AIS. If the goal is maximum impact and you accept messier input data, point the bbox here. Note: Hormuz is a chokepoint, so the asset layer there is shipping lanes, not cables.

The one hard constraint, whichever you pick: the chosen bounding box and time window must have both AIS coverage and at least one SAR pass. Confirm that overlap in Phase 0 before building anything. It is the only real scoping risk in the project.

## 5. Data sources

**AIS (choose per region):**

- **AISStream.io** — free global live WebSocket. Works for any bbox including Hormuz. Live only, so you record the stream to your database to build a replayable history. This is the default for location flexibility.
- **Fintraffic / Digitraffic** — free, CC-BY, Gulf of Finland and Finnish waters. Live oriented. Use if you commit to the Gulf of Finland.
- **Danish Maritime Authority** — free clean historical daily CSV, western Baltic only. Use if you want guaranteed historical AIS for replay without recording a live window.

**SAR (the second source):**

- **Global Fishing Watch API** — free token, precomputed Sentinel-1 vessel detections, global and historical. Each detection is a point with a scene timestamp and estimated length. This is the core path: you get the second data source without doing any image processing. Pull SAR detections yourself and do the AIS matching yourself, since the matching is the project's value. Do not consume GFW's own matched/unmatched flag as your answer.
- **Copernicus Data Space (Sentinel-1 GRD)** — free raw radar scenes. Only if you later build your own ship detector (CFAR or a small CNN). Optional flex that suits a CV background.

**Asset geometry (for the behavioral layer, the suspicion score, and the visuals):**

- Submarine cable routes from EMODnet (Europe) or TeleGeography (open GeoJSON), and/or shipping-lane polygons. Required for Section 9; also raises the suspicion score when a dark contact sits over an asset.

> Temporal-overlap reminder: the fusion needs AIS that covers the instant of the SAR scene. The cleanest path is a historical AIS source plus GFW SAR for the same date and bbox (guaranteed overlap, replayable). The flexible path is recording AISStream live over your bbox for a window and pulling SAR for that same window.

## 6. Tech stack


| Layer             | Choice                                               | Why                                                                                   |
| ----------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Backend language  | Python 3.11+                                         |                                                                                       |
| Database          | PostgreSQL 15+ with PostGIS 3.x                      | Spatial proximity, asset distance, and SAR-to-AIS matching are first-class.           |
| AIS ingest        | `websockets`/`httpx` (AISStream), Polars for any CSV |                                                                                       |
| Geometry          | Shapely, GeoPandas                                   | Track interpolation, distance, asset proximity.                                       |
| DB access         | asyncpg or SQLAlchemy 2.x                            | Async suits the live/replay stream.                                                   |
| Backend framework | FastAPI + uvicorn                                    | REST + WebSocket in one app.                                                          |
| SAR detections    | GFW REST API via `httpx`                             | GFW's official client is R-only; call REST from Python.                               |
| Frontend          | React + Vite + TypeScript                            |                                                                                       |
| Map               | deck.gl over MapLibre GL JS                          | Operational feel, free, no token. Free basemap: CARTO dark / OpenFreeMap / Protomaps. |
| Containers        | Docker + docker-compose                              | PostGIS + backend.                                                                    |


## 7. Data model

Geometry in WGS84 (EPSG:4326). Distance math in `geography` or projected metric CRS (EPSG:3035 for Europe; pick an appropriate UTM zone for other regions). Never compute distance in degrees.

```sql
CREATE TABLE vessel (
  mmsi BIGINT PRIMARY KEY, imo BIGINT, name TEXT, callsign TEXT,
  ship_type TEXT, length_m REAL, width_m REAL, flag TEXT, updated_at TIMESTAMPTZ
);

-- AIS positions (source 1)
CREATE TABLE ais_position (
  id BIGSERIAL PRIMARY KEY, mmsi BIGINT NOT NULL, t TIMESTAMPTZ NOT NULL,
  geom GEOMETRY(Point,4326) NOT NULL, sog REAL, cog REAL, heading REAL, nav_status TEXT
);
CREATE INDEX ix_pos_mmsi_t ON ais_position (mmsi, t);
CREATE INDEX ix_pos_geom   ON ais_position USING GIST (geom);

-- SAR detections (source 2)
CREATE TABLE sar_detection (
  id BIGSERIAL PRIMARY KEY, source TEXT NOT NULL, scene_id TEXT,
  t TIMESTAMPTZ NOT NULL, geom GEOMETRY(Point,4326) NOT NULL,
  length_m REAL, confidence REAL
);
CREATE INDEX ix_sar_geom ON sar_detection USING GIST (geom);
CREATE INDEX ix_sar_t ON sar_detection (t);

-- The fusion output: one row per SAR detection after matching
CREATE TABLE contact (
  id BIGSERIAL PRIMARY KEY,
  sar_detection_id BIGINT REFERENCES sar_detection(id),
  classification TEXT NOT NULL,        -- 'matched' | 'dark' | 'ambiguous'
  matched_mmsi BIGINT,                 -- NULL when dark
  match_distance_m REAL, match_dt_s REAL,
  predicted_from_gap BOOLEAN DEFAULT FALSE,  -- re-identified via dead-reckoning
  suspicion REAL,                      -- 0..1 score
  reason TEXT, details JSONB,
  t TIMESTAMPTZ, geom GEOMETRY(Point,4326)
);
CREATE INDEX ix_contact_geom ON contact USING GIST (geom);

-- Asset context (cables, lanes, zones)
CREATE TABLE asset (
  id SERIAL PRIMARY KEY, name TEXT, kind TEXT,  -- 'cable' | 'lane' | 'zone'
  geom GEOMETRY(Geometry,4326) NOT NULL, buffer_m INTEGER DEFAULT 2000
);
CREATE INDEX ix_asset_geom ON asset USING GIST (geom);

-- AIS-only behavioral anomalies near an asset (Section 9)
CREATE TABLE behavior_event (
  id BIGSERIAL PRIMARY KEY,
  mmsi BIGINT NOT NULL,
  asset_id INTEGER REFERENCES asset(id),
  rule TEXT NOT NULL,                  -- 'loiter' | 'anchor_drag' | 'slow_crossing' | 'type_mismatch'
  severity TEXT,                       -- 'low' | 'medium' | 'high'
  t_start TIMESTAMPTZ, t_end TIMESTAMPTZ,
  geom GEOMETRY(Geometry,4326),        -- the track segment that tripped the rule
  reason TEXT, details JSONB
);
CREATE INDEX ix_behavior_geom ON behavior_event USING GIST (geom);

```

## 8. Fusion and prediction logic (the heart)

All deterministic. Thresholds live in one config module as tunable defaults.

```python
# config/thresholds.py  (fusion)
SAR_MATCH_RADIUS_M       = 750     # SAR detection "explained" by an AIS vessel within this distance
SAR_MATCH_TIME_WINDOW_S  = 600     # AIS position interpolated to within this of scene time
GAP_MIN_S                = 900     # AIS silence (15 min) that counts as going dark
DR_MAX_PROJECTION_S      = 7200    # max time to dead-reckon a dark vessel forward (2 h)
SUSPICION_ASSET_BONUS    = 0.3     # added when a dark contact sits over an asset

```

### 8.1 Predict AIS positions to the SAR instant

A SAR scene is an instant at time `T`; AIS is discrete reports. For every vessel with AIS near `T`:

- If reports bracket `T`, **interpolate** position to `T` (linear on lat/lon is fine at these scales).
- If the vessel's last report is before `T` and within `DR_MAX_PROJECTION_S` (it went dark), **dead-reckon**: project position forward from last known point using its last course and speed. Flag this as a predicted (not observed) position.

This prediction step is what links the two sources. Interpolation handles normal vessels; dead-reckoning handles the ones that just went dark, and is the basis for re-identification below.

### 8.2 Match SAR detections to predicted AIS positions

For each `sar_detection`:

1. Find candidate predicted AIS positions within `SAR_MATCH_RADIUS_M` and `SAR_MATCH_TIME_WINDOW_S`.
2. If one or more match, classify `matched`, record `matched_mmsi`, distance, and dt.
3. If none match, classify `dark`. This is the headline output: a vessel in radar with no AIS.

### 8.3 Re-identify dark contacts (prediction payoff)

For each `dark` contact, check whether a recently-gone-dark vessel's dead-reckoned position lands near it (within a looser radius). If so, set `predicted_from_gap = TRUE` and attach the suspected `mmsi`. This is the strongest possible statement: "this radar blip is the vessel that switched off its AIS 40 minutes ago, here." It fuses the gap signal and the radar signal into one identified dark ship.

### 8.4 Suspicion score

A 0-to-1 score per contact so the UI can rank. Start simple and explainable:

- Base for being dark at all.
- Bonus if `predicted_from_gap` (a known vessel deliberately went dark).
- `SUSPICION_ASSET_BONUS` if the contact sits within an asset buffer (over a cable, in a lane).
- Bonus for persistence: the same location goes dark across multiple SAR passes. Keep the formula transparent; this is a ranking aid, not a verdict.

### 8.5 Spoofing (stretch)

The inverse gap: an AIS track claiming a position where a SAR scene shows open water. Harder (SAR misses small craft, coverage edges) and full of false positives, so it is a later, clearly-caveated addition, not part of the core.

## 9. Asset-anomaly behavioral layer (AIS-only)

The fusion above is the hero. This layer is a thin addition that makes the product concrete for a specific mission: protecting a named asset such as an undersea cable. It is almost entirely an AIS job, because the vessels that damage cables are usually still broadcasting while they do it. The Baltic cable-cutters (Eagle S, Yi Peng 3, NewNew Polar Bear, Fitburg) were tracked on AIS during or right after the act. So these rules need no SAR. They run on the vessel tracks you already store, and are evaluated only when a vessel is within `ASSET_PROXIMITY_M` of an asset, so they cost almost nothing on top of the existing pipeline.

SAR connects to this layer at exactly one joint, and it is the valuable one. See Section 9.2.

```python
# config/thresholds.py  (asset behavioral layer, AIS-only)
ASSET_PROXIMITY_M        = 2000    # only evaluate near-asset rules within this distance of an asset
LOITER_MAX_SOG_KN        = 3.0
LOITER_MIN_DURATION_S    = 1800    # 30 min
DRAG_SOG_MIN_KN          = 0.5
DRAG_SOG_MAX_KN          = 5.0
DRAG_MIN_TRACK_KM        = 10

```

### 9.1 Rules (evaluated only near an asset)

- **Loiter over asset.** Sustained `sog < LOITER_MAX_SOG_KN` for at least `LOITER_MIN_DURATION_S` while within the asset buffer. Use PostGIS `ST_DWithin` for the proximity test.
- **Anchor-drag signature.** A sustained low-speed run (`DRAG_SOG_MIN_KN..DRAG_SOG_MAX_KN`) whose continuous track length exceeds `DRAG_MIN_TRACK_KM` while paralleling or crossing the asset within its buffer, especially when nav status is not "at anchor." A vessel genuinely at anchor does not travel 10+ km. Compute track length on the projected geometry.
- **Slow crossing.** The vessel crosses the asset corridor at unusually low speed relative to its transit speed before and after, a softer signal that complements loiter.
- **Type / behavior mismatch.** Declared ship type inconsistent with behavior, e.g. a cargo ship or tanker loitering over a corridor with no port or anchorage to justify it. Keep v1 simple; this rule mainly raises the severity of the others.

Each event is explainable and AIS-only. Write the contributing values into `details` and a plain-English `reason`. These are ranked flags, not verdicts: a fishing vessel or a ship sheltering from weather can legitimately loiter, so present them with their reason and let a human judge.

### 9.2 The synergy joint (dark near asset)

This is the one place the two sources combine for the asset use case, and it is the strongest alert the whole system can produce. The sequence:

1. A vessel goes dark on AIS while within the asset buffer (a gap, Section 8.1, near an asset). AIS is now blind: it cannot tell whether the vessel parked over the corridor or left.
2. The next SAR pass produces a `dark` contact (Section 8.2) sitting over that same asset.
3. Dead-reckoning re-identifies the contact as the vessel that went dark (Section 8.3).

When all three line up, emit a top-severity alert: a known vessel deliberately went dark over the protected asset, and radar confirms it is still there. This falls out of the existing fusion plus the `SUSPICION_ASSET_BONUS`; the behavioral layer simply gives it an asset-focused framing and the surrounding context (was it loitering before it went dark?).

Honest framing for any demo: the behavioral rules carry the cable-protection story on AIS alone, because that is how the real incidents were actually caught. SAR earns its place at the dark moment, when AIS cannot see what a silenced ship is doing. Do not oversell SAR's role in the cable case; sell it precisely where it is irreplaceable.

## 10. API

WebSocket `/ws/replay` — server pushes `ais` position events, `sar` detection events (at scene time during replay), `contact` events (matched/dark with reason), and `behavior` events (asset anomalies). Client sends play/pause/seek/speed.

REST — `GET /scenarios`, `GET /vessels/{mmsi}/track`, `GET /sar?scenario_id=`, `GET /contacts?classification=dark`, `GET /behavior?asset_id=`, `GET /assets`.

## 11. Frontend (the comparison is the visualization)

deck.gl over a MapLibre dark basemap. The design goal is to make the gap between the two sources legible at a glance.

Layers:

- AIS vessels (`ScatterplotLayer`/`IconLayer`), oriented by heading, muted color.
- SAR detections (distinct radar-style glyph). Matched detections muted; **dark contacts bright and unmistakable**.
- Thin connector lines drawn between matched SAR-AIS pairs, so "matched" is visible and "dark" is the detection with no line.
- Dead-reckoned predicted tracks for gone-dark vessels (dashed), terminating at the SAR contact when re-identified.
- Asset layer (cables/lanes) drawn under everything, with the buffer faintly shaded so near-asset is visible.
- Behavioral flags highlighted on the offending track segment.

UI: replay controls (play/pause/speed/scrub), a unified event feed (dark contacts and behavioral flags) ranked by severity/suspicion with plain-English reasons, a toggle to show all SAR vs dark-only, and a vessel/contact detail card.

Selling interaction: scrub to a SAR pass. Most radar blips snap to an AIS vessel with a connector line. One does not. It lights up. The panel says: vessel X was loitering over the cable, went dark here 38 minutes ago, dead-reckoning put it right where radar now sees an unlinked contact.

## 12. Repository structure

```
darkwake/
  docker-compose.yml
  README.md
  DARKWAKE_SPEC.md
  backend/app/
    main.py
    config/ { thresholds.py, settings.py, aoi.py }   # aoi.py holds the bbox
    ingest/ { ais_stream.py, ais_csv.py, sar_gfw.py, assets.py }
    db/ { models.py, migrations/ }
    fusion/ { predict.py, match.py, score.py }        # the core
    detection/ { gaps.py, behavior.py, tests/ }       # AIS gap/dark + asset behavioral rules
    replay/ { clock.py, streamer.py }
    api/ { ws.py, rest.py }
  frontend/src/ { App.tsx, map/, components/, ws/, api/ }
  scripts/ { spike_overlap.py, pull_sar.py }

```

## 13. Phases

Build in order. Do not start a phase until the prior one meets its definition of done.

### Phase 0 — Overlap spike (the gate)

**Goal:** prove you have both data sources for one bbox and window before building. **Tasks:** pick the bbox and a date. Get AIS for it (record an AISStream window, or pull DMA/Fintraffic). Pull GFW SAR detections for the same bbox and date. Confirm spatially and temporally that a SAR scene falls inside your AIS coverage window. **Done when:** you can show, for one moment, a set of AIS positions and a set of SAR detections over the same water. If they do not overlap, change the date or bbox now, before anything is built.

### Phase 1 — Visualization

**Goal:** AIS on a map, replayable. No fusion yet. **Tasks:** Docker + PostGIS; AIS loader; replay clock + WebSocket streamer; deck.gl + MapLibre rendering vessels with replay controls. **Done when:** play the window and watch real vessels move over the AOI.

### Phase 2 — AIS-side detection and prediction

**Goal:** detect going dark, and predict where a dark vessel went. **Tasks:** implement gap detection (`detection/gaps.py`); implement interpolation and dead-reckoning (`fusion/predict.py`), test-first with synthetic fixtures. **Done when:** the system flags AIS gaps and can draw a dead-reckoned predicted track for a vessel after it goes silent.

### Phase 3 — SAR fusion (the headline)

**Goal:** the comparison. Matched vs dark. **Tasks:** SAR loader (`ingest/sar_gfw.py`); the matcher (`fusion/match.py`) using the predicted positions from Phase 2; write results to `contact`; render the SAR layer with connector lines and bright dark-contacts. **Done when:** replaying a SAR pass shows most detections linked to AIS vessels and at least one real dark contact (radar, no AIS) highlighted on the map.

### Phase 4 — Re-identification, scoring, context

**Goal:** turn raw dark contacts into ranked, explained, sometimes-identified detections, and load the asset layer. **Tasks:** re-identification via dead-reckoning (Section 8.3); suspicion score (`fusion/score.py`); load assets (`ingest/assets.py`) and apply the asset bonus; contact feed ranked by suspicion with reasons. **Done when:** the feed ranks dark contacts, at least one is re-identified to a vessel that went dark, each carries a plain-English reason, and assets are drawn on the map.

### Phase 5 — Asset-anomaly behavioral layer

**Goal:** the AIS-only cable-protection rules, plus the dark-near-asset fused alert. **Tasks:** implement the behavioral rules (`detection/behavior.py`), test-first with synthetic fixtures (a track that should and should not trip each rule); write `behavior_event` rows; wire the dark-near-asset synergy (Section 9.2) so a gap-near-asset plus a dark contact over the asset plus a re-identification surfaces as a top-severity alert; show behavioral flags and the unified feed in the UI. **Done when:** replaying shows at least one real near-asset behavioral flag (e.g. a vessel loitering over a corridor) with a reason, and when the data contains a dark-near-asset case it surfaces as the top-ranked alert with all three contributing reasons.

### Phase 6 — Optional flexes (future)

Own SAR detector (Copernicus + CFAR or a small CNN); spoofing detection (the inverse gap); live mode (continuous AISStream ingest); an "action" cueing slide. None are required for the thesis.

## 14. Working with the AI agent

- One phase at a time, each shippable. Do not let the agent build the matcher before prediction, score before matching, or behavioral rules before the asset layer is loaded.
- Prediction, matching, and every behavioral rule are built test-first, each with a passing and a failing fixture.
- All thresholds in `config/thresholds.py`. The bbox in `config/aoi.py`. No magic numbers in logic.
- Geometry discipline: store 4326, distance in `geography`/metric CRS, never degrees.
- Keep the AOI and window small in dev.
- A dark contact and a behavioral flag are candidates, not convictions. Label them that way everywhere.
- Honesty over theater: the value is real, unplanted comparison and detection on real data. Never fabricate a dark contact or an anomaly.

## 15. North-star demo script

Roughly 90 seconds, hero first:

"Two independent sources. AIS, what ships broadcast about themselves. And SAR, what a satellite's radar actually sees. Watch a radar pass land. Most detections snap to a broadcasting vessel, connector line drawn, all accounted for. This one has no line. There is a ship right here that is telling no one. And here is the part that makes it a detection and not a guess: this vessel was loitering over the cable, then went dark on AIS 38 minutes ago. My system dead-reckoned where it should be, and that is exactly where radar now sees an unlinked contact. AIS said it vanished. Radar says it is right here, sitting on the cable."

The asset framing rides on the same moment: the behavioral rules raise the flag on AIS, and SAR confirms what the silenced ship is doing.

## 16. Risks and open questions

- The one hard constraint is AIS-and-SAR overlap for your chosen bbox and window. Settle it in Phase 0.
- SAR is a snapshot every 1 to 3 days, so dark detection is per-pass, not continuous. Say so in the demo.
- SAR false positives (sea clutter, small craft, winter sea ice in northern waters). Starting from GFW's classified detections mitigates this; keep a confidence filter.
- Dead-reckoning degrades over time; cap the projection window and show uncertainty.
- Behavioral rules describe behavior, not intent; legitimate vessels can trip them. Present flags with reasons, ranked, never as verdicts.
- The famous cable incidents were mostly caught on AIS, not because the ships were invisible. The behavioral layer carries that story; SAR is for the dark moment specifically. Frame it honestly.
- If using AISStream live, you must record a window before you have anything to replay. If you want zero-wait historical data, use DMA (western Baltic) for the AIS side.
- Match radius, time window, and behavioral thresholds need tuning against real data; budget time and keep notes on calls.

