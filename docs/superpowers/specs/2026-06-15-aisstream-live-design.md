# AISStream Live Mode — Design Spec

**Date:** 2026-06-15  
**Status:** Approved (Approach A — live-primary, replay retained)

## Goal

Shift DarkWake from replay-first to **live-first** using AISStream.io for real-time AIS, while keeping historical replay for demos and operator incident review. Persist history only when anomalous events occur. Maintain **AIS + SAR** as dual modalities on the map.

## Architecture

```
AISStream (wss) ──► ais_stream.py ──► LiveHub ──► /ws/live ──► Frontend
                         │                │
                         │                ├── VesselRegistry (in-memory)
                         │                ├── Rolling track buffers (ephemeral)
                         │                ├── Gap / behavior detectors
                         │                └── operator_event (PostGIS, on alert)
GFW SAR poller ──────────┘                └── /ws/replay (unchanged, DB-backed)
```

### Ephemeral vs persisted

| Data | Storage | TTL |
|------|---------|-----|
| Latest vessel positions | In-memory registry | Until process restart |
| Movement trails | Per-vessel deque | Configurable window (default 6 h) |
| Normal AIS reports | Not stored | — |
| Alerts (gaps, dark, behavior) | `operator_event` + track excerpt | Permanent |
| Historical replay | `ais_position` table | Existing Phase 1 path |

### WebSocket protocols

**`/ws/live`** (new, default frontend mode):
- Server pushes: `live_state`, `ais` / `ais_batch`, `tracks_batch`, `alert`, `sar_batch`
- Client: no required messages (optional `ping`)

**`/ws/replay`** (retained):
- Unchanged — play/pause/seek over loaded DB positions

### Alert kinds (v1)

1. `ais_gap` — vessel silent ≥ `GAP_MIN_S` (900 s)
2. `behavior` — reserved for Phase 5 asset rules
3. `dark_contact` — reserved for Phase 3 SAR fusion
4. `sar` — SAR detection broadcast (informational until fusion)

### SAR in live mode

GFW poller runs on a background interval (default 1 h). New detections are broadcast to live clients and shown on the map. Full AIS–SAR matching remains Phase 3; the poller wires the second modality now.

### Frontend modes

- **Live** (default): connects to `/ws/live`, hides timeline scrubber, shows LIVE badge
- **Replay**: connects to `/ws/replay`, shows timeline dock
- Mode via `?mode=replay` query param or in-app toggle

## Non-goals (this phase)

- Full SAR fusion matcher (Phase 3)
- Asset behavioral rules (Phase 5)
- Replacing replay code paths
- Browser-direct AISStream connection (API key stays server-side)

## Config

| Setting | Location | Default |
|---------|----------|---------|
| AISStream API key | `AISSTREAM_API_KEY` env | required for live |
| Track buffer | `LIVE_TRACK_BUFFER_HOURS` | 6 |
| SAR poll interval | `SAR_POLL_INTERVAL_S` | 3600 |
| Gap threshold | `GAP_MIN_S` in thresholds.py | 900 |

## Success criteria

1. With valid `AISSTREAM_API_KEY`, backend ingests live AIS for the AOI bbox
2. Frontend shows moving vessels in live mode without DB load
3. AIS gap events are detected, persisted to `operator_event`, and shown in event feed
4. SAR detections appear on the map in live mode
5. Replay mode still works with existing loaded data
