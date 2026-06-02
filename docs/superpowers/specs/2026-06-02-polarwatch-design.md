# PolarWatch — Dark Vessel Detection for the Polar & Northern Seas

**Project Plan & Technical Specification**

Author: Sierra Ryan · Date: 2026-06-02 · Version: 2.0

A portfolio project in maritime domain awareness: real-time multi-sensor anomaly detection and an operator-grade common operating picture, built end-to-end on free, openly-licensed data.

> **Status note (this repo):** This document is the authoritative design spec. The **first implementation plan is scoped to Phase 0–1 only** (Foundation: repo, Docker Compose, data keys, README skeleton, AIS ingest, track builder, clock-driven replay). Phases 2–8 remain the agreed roadmap and will each get their own plan after the foundation is built and verified.

---

## 1. Goal & One-Line Pitch

PolarWatch ingests open AIS vessel-tracking data for the Arctic and northern seas, fuses it with a second (simulated radar/SAR) sensor, detects "dark" and anomalous vessel behavior with a layered detection engine, and represents every vessel and alert in a unified entity model surfaced on a polished, operator-grade common operating picture (COP).

A "dark vessel" is a ship that should be broadcasting its position via AIS but isn't — its transponder is off, it is spoofing a false position or identity, or it is operating where it assumes no one is watching. In the polar and northern seas this matters disproportionately: sanctions evasion by the Russian "shadow fleet" in the Barents and Norwegian Seas, illegal fishing near Svalbard, undersea cable and pipeline tampering, and search-and-rescue gaps all hinge on knowing which ships have gone quiet — and why.

The project is scoped so one person can build it end-to-end on free data, while demonstrating the capabilities that matter most for command-and-control and autonomy work: an entity-centric data model, real-time multi-sensor fusion, evaluated anomaly detection, and a striking operator-grade interface.

## 2. Design Principles & What This Demonstrates

PolarWatch is deliberately built around the capabilities that defense-technology and C2 reviewers screen for — described in standard, vendor-neutral terms so the project stands on its own engineering merits.

| Capability | How PolarWatch demonstrates it |
|---|---|
| Entity-centric common data model | Every vessel, sensor contact, and alert is a typed entity with ID, location, kinematics, classification, provenance, confidence, and expiry. |
| Multi-sensor fusion | A second sensor stream is correlated against AIS; unmatched contacts become dark-vessel detections AIS alone can't produce. |
| Real-time streaming | A clock-driven replay engine drives the whole pipeline as a live feed (pause, rewind, speed up). |
| Common operating picture | An operator-grade map UI with live tracks, a time slider, fused contacts, and explainable alerts. |
| Decision-quality alerting | Every alert is scored and carries a one-sentence reason; false-positive rate is measured, not ignored. |
| Engineering rigor | Tested code, an evaluation harness with real precision/recall, latency metrics, and one-command Docker deploy. |

**What a reviewer should conclude**

"This person can build a mission-relevant, fused, real-time sensing system with production-minded engineering discipline — and made sound architectural choices under a realistic data constraint." The entity model and fusion layer are designed as clean interfaces, so the system could be repointed at a production C2 / common-data-model backend without changing the detection or UI.

## 3. The Entity-Centric Operating Picture

### 3.1 Why an entity model

Rather than passing raw rows between stages, PolarWatch normalizes everything real-world into Entities: a vessel, a radar/SAR contact, or an alert is each a typed object with a stable ID, location, kinematic state (heading, speed), classification/ontology (e.g. `SURFACE_VESSEL`), provenance (which sensor saw it), a confidence, an expiry time, and aliases (MMSI/IMO/name). This is the same common-data-model pattern modern command-and-control platforms use, and it is what makes fusion and a coherent operating picture possible — different sensors describe the same world in one shared vocabulary.

The entity store exposes a small gRPC/REST interface (publish, query, subscribe). Keeping it behind a clean contract is deliberate: the detection engine and UI never know or care what backs it, so it could later be swapped for a production entity backend with no downstream changes.

### 3.2 The detection problem, precisely

"Dark vessel" is an umbrella. The engine targets concrete, individually-evaluable behaviors:

| Behavior | Signal | Why it matters |
|---|---|---|
| AIS gap / going dark | Normal transmission stops, then resumes — a temporal hole inconsistent with coverage. | Concealment around illicit fishing, transfers, sanctioned port calls. |
| Position spoofing | Reported position jumps, implies impossible speed, sits on land, or circles a fixed point. | Identity laundering and decoy tracks; GPS/AIS manipulation. |
| Loitering / drifting | Sustained low speed in open water with no port or anchorage. | Staging for a rendezvous or near cables/pipelines/borders. |
| Rendezvous (STS) | Two vessels converge, slow, hold proximity, then separate. | Ship-to-ship transfer to obscure cargo origin. |
| Identity tampering | MMSI/IMO/name/flag change mid-track, or duplicate MMSI in two places. | Flag-hopping and identity reuse by shadow-fleet vessels. |
| Unmatched sensor contact | A radar/SAR detection with no corresponding AIS track. | The purest dark-vessel signal — surfaced only by fusion. |

## 4. System Architecture

A streaming pipeline with two sensor inputs feeding a fusion stage, a detection engine, and an entity store that both the API clients and the UI read from.

| Stage | Responsibility | Representative tech |
|---|---|---|
| 1a. AIS ingest | Replay open AIS as a live stream; normalize to a common schema. | Python, pyarrow, aiohttp; GeoParquet |
| 1b. Sensor-2 ingest | Generate/replay simulated radar/SAR contacts (some matching AIS, some dark). | Python; GFW SAR detections (stretch) |
| 2. Track + fusion | Build per-vessel tracks; correlate the two sources; flag unmatched contacts. | GeoPandas, Shapely; nearest-neighbor association |
| 3. Detect | Layered anomaly engine over rolling windows; emit scored, explainable events. | scikit-learn, PyTorch, rule layer |
| 4. Entity store | Publish vessels + alerts as entities through a gRPC/REST entity service. | FastAPI + grpcio; Redis + PostGIS |
| 5. Visualize | Render the COP: map, tracks, time slider, fusion overlay, alert feed. | React + deck.gl + MapLibre GL |

Historical AIS is replayed through a clock-driven engine so the demo behaves like a live feed without a paid real-time source. Detection writes to the same entity store the UI reads, so nothing in the visualization is pre-baked.

## 5. Data Strategy

Everything runs on free, openly-licensed data. Note up front: U.S. NOAA/MarineCadastre AIS is excellent but largely stops at the coast and does not cover the Arctic, so the polar focus relies on Northern-European open feeds and satellite-AIS-derived datasets.

| Source | Coverage | Role | Cost |
|---|---|---|---|
| Kystverket / BarentsWatch (Norway) | Norwegian + Barents Sea, Svalbard | Primary AIS; best open coverage of the target region. | Free (API key) |
| Danish Maritime Authority AIS | Danish & Baltic waters | Secondary northern-seas coverage; bulk history. | Free |
| Global Fishing Watch | Global (sat-AIS + SAR detections) | Weak labels + SAR contacts for the fusion sensor. | Free (API) |
| NOAA MarineCadastre (AccessAIS) | U.S. coastal | Clean dev sandbox to build the pipeline first. | Free |
| Synthetic sensor-2 generator | Target region | Radar/SAR contacts (matched + dark) for fusion demo. | Self-generated |

### 5.1 Turning sparse coverage into the core idea

The hard part of dark-vessel detection is distinguishing a genuine "went dark" event from a mere coverage gap. PolarWatch models expected coverage explicitly: a vessel that disappears inside a well-covered cell is suspicious; one that vanishes at the edge of coverage probably is not. Treating this honestly — and writing about it — is what separates a credible system from a toy.

## 6. Entity Store & Operating-Picture Layer

The connective tissue that makes the project read as a coherent system rather than a one-off script.

- **Typed entity schema:** `entityId`, `expiryTime`, `provenance`, `location`, `kinematics`, ontology/classification (`SURFACE_VESSEL`, `SENSOR_CONTACT`, `ALERT`), `confidence`, and `aliases` (MMSI/IMO/name).
- **Small, clean API:** publish (create-or-update), query, and subscribe — exposed over both REST and gRPC.
- **Alerts as entities:** each detection is its own geo-located entity linked to the vessel — the way an operator-facing system surfaces findings.
- **Swappable backend:** FastAPI + grpcio with Redis (current state) and PostGIS (history). Because it sits behind a clean contract, it could be replaced by a production common-data-model backend without touching detection or UI.

## 7. Detection & Fusion Engine (Core)

The half that must be unimpeachable. Principle: a layered detector — cheap, explainable rules first; statistical/ML models for the subtle cases; and cross-sensor fusion for the contacts AIS alone can never see. Every alert carries a score and a one-sentence reason.

### 7.1 Layer 1 — Deterministic rules (baseline)

- **Kinematic implausibility:** implied speed between points exceeds a vessel-class ceiling → spoof/jump.
- **On-land / fixed-point oscillation:** reported position is physically impossible.
- **AIS gap:** silence beyond T inside a modeled-covered cell, with feasible-travel reasoning on reappearance.
- **Loitering:** low speed-over-ground sustained outside any port/anchorage polygon.
- **Identity flags:** MMSI/IMO/name/flag change mid-track, or duplicate MMSI seen in two places at once.

### 7.2 Layer 2 — Statistical & ML detection

| Method | What it catches | Notes |
|---|---|---|
| Isolation Forest / LOF on engineered features | Point/segment outliers in speed, turn-rate, gap-length, distance-to-coast. | Unsupervised, fast, strong ML baseline. |
| LSTM / Transformer trajectory model | Tracks deviating from learned "normal" routes (high prediction error = anomaly). | Trained on bulk normal tracks. |
| Sequence autoencoder | Whole-track anomalies and novel movement patterns. | Reconstruction-error thresholding. |
| Rendezvous detector (spatiotemporal join) | STS meetings: converge, slow, hold, separate. | Distance + dwell + feasible-envelope logic. |
| DBSCAN on stop-points | Loitering clusters and recurring meeting hot-spots. | Surfaces repeated locations. |

### 7.3 Layer 3 — Multi-source fusion & cross-cueing (the differentiator)

The layer that demonstrates real sensing-system thinking: turning many sensors into one picture. A second sensor stream (simulated radar/SAR contacts; real GFW SAR detections as a stretch) is correlated against AIS tracks by position and time.

- **Unmatched contact = dark vessel:** a radar/SAR return with no AIS track within an association radius is the strongest possible dark-vessel signal and cannot be produced by AIS analysis alone.
- **Corroboration raises confidence:** a contact matching an AIS track confirms it; a contact matching a track that just went dark is a high-severity alert.
- **Single entity model:** both sensors publish into the same entity store, so fusion is expressed in shared terms — provenance, confidence, and a fused track.

Even simulated, this feature does more to signal sensing-system competence than any single model choice — it demonstrates the core sensor-fusion value proposition directly.

### 7.4 Features

Per-point and per-window features: speed-over-ground, course-over-ground, rate-of-turn, acceleration, segment length/duration, time-since-last-message, distance to nearest coast/port/anchorage, distance to nearest vessel, message density vs. modeled coverage, identity-stability flags, and distance to nearest unmatched sensor contact.

### 7.5 Labels, training & honesty about truth

Three complementary truth sources: (1) **synthetic injection** — inject gaps, jumps, loiters, rendezvous, and dark contacts into clean tracks for exact labels and a real confusion matrix; (2) **Global Fishing Watch events and SAR detections** as weak/partial real labels; (3) **self-consistency** — physics-violating spoofs are unambiguous without external labels. Synthetic injection is the backbone of the evaluation.

## 8. Visualization & UI (Core)

The COP is what a reviewer sees first, so it must read as a real operations console. Target aesthetic: dark, high-contrast, Arctic — near-black map, luminous tracks, glowing alerts, restrained typography, live motion.

### 8.1 Layout

- **Map canvas (center):** dark Arctic basemap; oriented vessel markers; fading track trails; pulsing alert markers; unmatched sensor contacts as a distinct symbol.
- **Time slider (bottom):** scrub, play, pause, speed up over the replayed feed — the single most impressive interaction.
- **Alert feed (right rail):** live, severity-sorted, one-sentence explainable; click to fly-to the vessel.
- **Vessel detail (drawer):** identity, track history, triggering features, AIS-gap mini-timeline, and any fused sensor contact.
- **Fusion overlay / filters (left):** toggle sensor-2 contacts and matched/unmatched state; filter by behavior, class, severity.

### 8.2 Technology

deck.gl (GPU geospatial layers) over MapLibre GL (free vector basemap, no key lock-in) in a React app. deck.gl's TripsLayer animates vessel trails cinematically; a polar-stereographic projection is a distinctive Arctic touch. State streams over a WebSocket from the entity store's subscribe endpoint.

Polish that punches above its weight: a consistent severity color ramp, smooth fly-to camera transitions, a vessel-count / active-alerts HUD, and a short auto-playing scenario on load that shows a vessel going dark and a radar contact appearing where its AIS dropped — selling the demo in the first five seconds.

## 9. Technology Stack (Summary)

| Layer | Choice |
|---|---|
| Language | Python (pipeline / ML / services), TypeScript (UI) |
| Entity layer | gRPC/REST entity service (FastAPI + grpcio) behind a clean, swappable contract |
| Ingest / data | pandas, pyarrow, GeoPandas, Shapely; GeoParquet |
| Detection / fusion | scikit-learn, PyTorch (LSTM/autoencoder), spatiotemporal association |
| State / history | Redis (current) + PostGIS (history) |
| Frontend | React, deck.gl, MapLibre GL, WebSocket |
| Infra / delivery | Docker Compose; demo on Fly.io / Render; pytest + eval harness + GitHub Actions CI |

## 10. Phased Roadmap

Sequenced for a demo-able result early, then depth. Estimates assume part-time solo work.

| Phase | Weeks | Deliverable | Done when |
|---|---|---|---|
| 0 — Setup | 0.5 | Repo, Docker Compose, data keys, README skeleton. | One command boots the empty stack. |
| 1 — Data + replay | 1–2 | AIS ingest, track builder, clock-driven replay. | A Barents Sea day replays through the pipeline. |
| 2 — Entity layer | 1 | gRPC/REST entity service: publish, query, subscribe. | Vessels publish as entities; a client streams them. |
| 3 — Detection v1 (rules) | 1–2 | Layer-1 rules emitting explainable alert entities. | Alerts appear in the entity store with reasons. |
| 4 — UI v1 | 2 | deck.gl COP: map, animated tracks, time slider, alert feed. | Live demo scrubs time and shows alerts firing. |
| 5 — Fusion | 1–2 | Sensor-2 generator + correlation + unmatched-contact alerts. | Dark contacts surface that AIS alone can't. |
| 6 — Detection v2 (ML) | 2–3 | Isolation Forest + trajectory model + rendezvous; eval harness. | Reported precision/recall vs. rule baseline. |
| 7 — Polish + portfolio | 1–2 | UI pass, demo video, write-up, deploy. | Public live demo + README + blog post. |
| 8 — Stretch | — | Real SAR (Sentinel-1 / GFW) into the fusion layer. | Real unmatched SAR contact cross-checked vs AIS. |

## 11. Evaluation & Metrics

"Solid anomaly detection" means numbers. The harness scores the engine against the synthetic-injection set and GFW weak labels.

- **Detection quality:** precision, recall, F1, PR-AUC per behavior type, plus a confusion matrix.
- **Baseline comparison:** ML and fusion layers vs. rules-only — show where each actually adds lift.
- **Fusion lift:** dark vessels caught by fusion that AIS analysis alone missed.
- **Calibration:** does alert score track true severity? Reliability curve.
- **Operational realism:** alerts per hour and false-positive rate — it can't cry wolf.
- **Latency:** ingest-to-published-alert time — proves it could run live.

## 12. Portfolio Packaging

Making the value legible is half the work. Ship all of:

- **Live hosted demo** with an auto-playing default scenario — the highest-leverage artifact.
- **90-second demo video** (scrub time, vessel goes dark, radar contact appears, alert fires, click to inspect).
- **README** with architecture diagram and the evaluation numbers up top.
- **A short write-up** on the hard idea: telling "went dark" apart from "out of coverage," and what fusion adds.
- **Clean, tested repo** with Docker Compose so it runs in one command.

README framing line: *"An open-data prototype of a maritime-domain-awareness pipeline — detects dark and anomalous vessel behavior in the Arctic, fuses two sensor sources, and presents them in a unified entity model and operating picture."*

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Polar AIS is sparse/noisy. | Develop on clean NOAA data first; model coverage explicitly; make gap-vs-dark a feature. |
| No real "illicit" ground truth. | Synthetic injection for exact labels; GFW + physics violations as partial real truth. |
| Scope creep (real SAR). | Real SAR is Phase 8 / stretch. Simulated sensor-2 delivers the fusion story first. |
| UI eats all the time. | Time-box a v1 (Phase 4), one polish pass (Phase 7); deck.gl defaults early. |
| Real-time performance at scale. | Profile early; cap message rate; precompute spatial indexes; keep the hot path simple. |

## 14. Key References & Sources

- BarentsWatch (Norwegian open AIS)
- NOAA MarineCadastre AccessAIS
- Global Fishing Watch — data & APIs
- deck.gl (geospatial visualization)
- MapLibre GL (open basemaps)
