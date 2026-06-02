# PolarWatch Phase 0–1 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the PolarWatch repo and a working data pipeline that ingests Barents-Sea AIS, builds per-vessel tracks, and replays a full day through a clock-driven engine — so "a Barents Sea day replays through the pipeline" is demonstrably true and one command boots the stack.

**Architecture:** A small Python package (`src/polarwatch`) with focused modules: a typed entity model (`AisPosition`, `VesselTrack`), pure normalization from raw AIS records, Parquet I/O, a deterministic synthetic-day generator (the reproducible test/demo fixture), a live BarentsWatch capture client (real OAuth2 + REST, network-isolated and mockable), a track builder, and a clock-driven replay engine with an injectable sleep for instant tests. A Typer CLI wires the stages (`synth-day → ingest → replay`, plus `capture` and `demo`). Docker Compose boots the app plus Redis and PostGIS placeholders (pre-wired for Phase 2's entity store).

**Tech Stack:** Python 3.11+, pydantic v2 (typed models + validation), pandas + pyarrow (Parquet), httpx (HTTP, mocked via `httpx.MockTransport`), Typer (CLI), pytest. Docker Compose for the stack. `geopandas`/GeoParquet are intentionally deferred to a later phase (spatial ops aren't needed yet; avoids GDAL weight) — plain Parquet with lat/lon columns suffices for Phase 0–1.

**Key design decisions (locked):**
- **Raw record shape is BarentsWatch-like** so the synthetic generator and the live client produce the *same* shape, and one `normalize_record` handles both: `{mmsi, latitude, longitude, speedOverGround, courseOverGround, trueHeading, name, msgtime}`.
- **Replay is testable** via an injected `sleep` callable — tests record sleep durations instead of waiting.
- **Network is isolated** — the BarentsWatch client takes an `httpx.Client`, so tests use `httpx.MockTransport` with zero real calls.
- **Data files are runtime artifacts** — everything under `data/` is gitignored.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, `polarwatch` console script, pytest/setuptools config |
| `.gitignore` | Ignore `data/`, `.env`, caches, venvs |
| `.env.example` | Document `BARENTSWATCH_CLIENT_ID` / `_SECRET` |
| `README.md` | Project intro, quickstart, architecture note |
| `Dockerfile` | Build the app image; default CMD runs the demo |
| `docker-compose.yml` | App + Redis + PostGIS (Phase 2 placeholders) |
| `src/polarwatch/__init__.py` | Package marker / version |
| `src/polarwatch/model.py` | `AisPosition`, `VesselTrack` typed models |
| `src/polarwatch/normalize.py` | `normalize_record(raw) -> AisPosition` (pure) |
| `src/polarwatch/parquet_io.py` | positions ⇄ Parquet; NDJSON read |
| `src/polarwatch/synth.py` | Deterministic synthetic Barents-Sea day generator |
| `src/polarwatch/barentswatch.py` | Live AIS capture: OAuth2 token + fetch positions |
| `src/polarwatch/tracks.py` | `build_tracks(positions) -> list[VesselTrack]` |
| `src/polarwatch/replay.py` | Clock-driven `replay(positions, speed, sleep)` generator |
| `src/polarwatch/cli.py` | Typer app: `synth-day`, `ingest`, `replay`, `capture`, `demo` |
| `tests/test_*.py` | One test module per source module + end-to-end |

---

## Task 1: Repo scaffolding & package skeleton

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `src/polarwatch/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `.gitignore`**

```
__pycache__/
*.pyc
.venv/
venv/
.env
data/
*.parquet
*.ndjson
.pytest_cache/
*.egg-info/
dist/
build/
```

- [ ] **Step 2: Create `.env.example`**

```
# BarentsWatch open AIS API credentials (register a client at https://www.barentswatch.no)
BARENTSWATCH_CLIENT_ID=
BARENTSWATCH_CLIENT_SECRET=
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "polarwatch"
version = "0.1.0"
description = "Dark vessel detection for the polar & northern seas"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.6",
    "pandas>=2.2",
    "pyarrow>=15.0",
    "httpx>=0.27",
    "typer>=0.12",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
polarwatch = "polarwatch.cli:app"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 4: Create `src/polarwatch/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: Create empty `tests/__init__.py`**

```python
```

- [ ] **Step 6: Create venv and install**

Run:
```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
```
Expected: installs polarwatch and pytest with no errors.

- [ ] **Step 7: Verify the package imports**

Run: `python -c "import polarwatch; print(polarwatch.__version__)"`
Expected: prints `0.1.0`

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/polarwatch/__init__.py tests/__init__.py
git commit -m "chore: scaffold polarwatch package skeleton"
```

---

## Task 2: Typed entity model (`AisPosition`, `VesselTrack`)

**Files:**
- Create: `src/polarwatch/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_model.py
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from polarwatch.model import AisPosition, VesselTrack


def _pos(mmsi=257000001, t=0, lat=70.0, lon=20.0):
    return AisPosition(
        mmsi=mmsi,
        timestamp=datetime(2026, 6, 1, 0, t, 0, tzinfo=timezone.utc),
        lat=lat,
        lon=lon,
    )


def test_position_minimal_fields_default_none():
    p = _pos()
    assert p.mmsi == 257000001
    assert p.sog is None and p.cog is None and p.heading is None and p.name is None


def test_position_rejects_out_of_range_lat():
    with pytest.raises(ValidationError):
        _pos(lat=120.0)


def test_position_rejects_out_of_range_lon():
    with pytest.raises(ValidationError):
        _pos(lon=200.0)


def test_track_computed_properties():
    positions = [_pos(t=0), _pos(t=5), _pos(t=10)]
    track = VesselTrack(mmsi=257000001, name="TEST", positions=positions)
    assert track.count == 3
    assert track.start_time == positions[0].timestamp
    assert track.end_time == positions[-1].timestamp
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'polarwatch.model'`

- [ ] **Step 3: Write the implementation**

```python
# src/polarwatch/model.py
from datetime import datetime

from pydantic import BaseModel, field_validator


class AisPosition(BaseModel):
    """A single normalized AIS position report for one vessel."""

    mmsi: int
    timestamp: datetime
    lat: float
    lon: float
    sog: float | None = None  # speed over ground, knots
    cog: float | None = None  # course over ground, degrees
    heading: float | None = None  # true heading, degrees
    name: str | None = None

    @field_validator("lat")
    @classmethod
    def _check_lat(cls, v: float) -> float:
        if not -90.0 <= v <= 90.0:
            raise ValueError(f"lat {v} out of range [-90, 90]")
        return v

    @field_validator("lon")
    @classmethod
    def _check_lon(cls, v: float) -> float:
        if not -180.0 <= v <= 180.0:
            raise ValueError(f"lon {v} out of range [-180, 180]")
        return v

    @field_validator("mmsi")
    @classmethod
    def _check_mmsi(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"mmsi {v} must be positive")
        return v


class VesselTrack(BaseModel):
    """All positions for one vessel (MMSI), ordered by time."""

    mmsi: int
    name: str | None = None
    positions: list[AisPosition]

    @property
    def count(self) -> int:
        return len(self.positions)

    @property
    def start_time(self) -> datetime:
        return self.positions[0].timestamp

    @property
    def end_time(self) -> datetime:
        return self.positions[-1].timestamp
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_model.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/polarwatch/model.py tests/test_model.py
git commit -m "feat: add AisPosition and VesselTrack models"
```

---

## Task 3: Record normalization (raw AIS → `AisPosition`)

**Files:**
- Create: `src/polarwatch/normalize.py`
- Test: `tests/test_normalize.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize.py
from datetime import datetime, timezone

from polarwatch.normalize import normalize_record


RAW = {
    "mmsi": 257000001,
    "latitude": 70.5,
    "longitude": 19.25,
    "speedOverGround": 12.3,
    "courseOverGround": 88.0,
    "trueHeading": 90,
    "name": "TEST VESSEL",
    "msgtime": "2026-06-01T00:00:00Z",
}


def test_normalize_maps_all_fields():
    p = normalize_record(RAW)
    assert p.mmsi == 257000001
    assert p.lat == 70.5 and p.lon == 19.25
    assert p.sog == 12.3 and p.cog == 88.0 and p.heading == 90.0
    assert p.name == "TEST VESSEL"
    assert p.timestamp == datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_normalize_tolerates_missing_optional_fields():
    p = normalize_record(
        {"mmsi": 257000002, "latitude": 71.0, "longitude": 20.0, "msgtime": "2026-06-01T01:00:00Z"}
    )
    assert p.sog is None and p.cog is None and p.heading is None and p.name is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'polarwatch.normalize'`

- [ ] **Step 3: Write the implementation**

```python
# src/polarwatch/normalize.py
from polarwatch.model import AisPosition


def normalize_record(raw: dict) -> AisPosition:
    """Map a raw BarentsWatch-shaped AIS record to a normalized AisPosition.

    The synthetic generator and the live BarentsWatch client both emit this
    shape, so this is the single normalization path for all ingest.
    """
    return AisPosition(
        mmsi=int(raw["mmsi"]),
        timestamp=raw["msgtime"],  # pydantic parses the ISO 8601 string
        lat=float(raw["latitude"]),
        lon=float(raw["longitude"]),
        sog=raw.get("speedOverGround"),
        cog=raw.get("courseOverGround"),
        heading=raw.get("trueHeading"),
        name=raw.get("name"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_normalize.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/polarwatch/normalize.py tests/test_normalize.py
git commit -m "feat: add raw AIS record normalization"
```

---

## Task 4: Parquet I/O & NDJSON reading

**Files:**
- Create: `src/polarwatch/parquet_io.py`
- Test: `tests/test_parquet_io.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_parquet_io.py
import json
from datetime import datetime, timezone

from polarwatch.model import AisPosition
from polarwatch.parquet_io import (
    read_ndjson_records,
    read_positions,
    write_positions,
)


def _pos(mmsi=257000001, minute=0, sog=None):
    return AisPosition(
        mmsi=mmsi,
        timestamp=datetime(2026, 6, 1, 0, minute, 0, tzinfo=timezone.utc),
        lat=70.0,
        lon=20.0,
        sog=sog,
    )


def test_write_then_read_roundtrips_positions(tmp_path):
    positions = [_pos(minute=0, sog=10.0), _pos(minute=1, sog=None)]
    path = tmp_path / "day.parquet"
    write_positions(positions, path)
    loaded = read_positions(path)
    assert len(loaded) == 2
    assert loaded[0].mmsi == 257000001
    assert loaded[0].sog == 10.0
    assert loaded[1].sog is None  # NaN must come back as None


def test_read_ndjson_records(tmp_path):
    path = tmp_path / "raw.ndjson"
    rows = [
        {"mmsi": 1, "latitude": 70.0, "longitude": 20.0, "msgtime": "2026-06-01T00:00:00Z"},
        {"mmsi": 2, "latitude": 71.0, "longitude": 21.0, "msgtime": "2026-06-01T00:01:00Z"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    records = list(read_ndjson_records(path))
    assert len(records) == 2
    assert records[0]["mmsi"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_parquet_io.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'polarwatch.parquet_io'`

- [ ] **Step 3: Write the implementation**

```python
# src/polarwatch/parquet_io.py
import json
from pathlib import Path
from typing import Iterator

import pandas as pd

from polarwatch.model import AisPosition


def write_positions(positions: list[AisPosition], path: str | Path) -> None:
    """Write normalized positions to a Parquet file."""
    frame = pd.DataFrame([p.model_dump() for p in positions])
    frame.to_parquet(path, index=False)


def read_positions(path: str | Path) -> list[AisPosition]:
    """Read positions back from Parquet, restoring None for missing values."""
    frame = pd.read_parquet(path)
    # Parquet/pandas represent missing floats as NaN; convert back to None.
    frame = frame.astype(object).where(pd.notnull(frame), None)
    return [AisPosition(**row) for row in frame.to_dict("records")]


def read_ndjson_records(path: str | Path) -> Iterator[dict]:
    """Yield raw records from a newline-delimited JSON capture file."""
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_parquet_io.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/polarwatch/parquet_io.py tests/test_parquet_io.py
git commit -m "feat: add Parquet I/O and NDJSON reader"
```

---

## Task 5: Synthetic Barents-Sea day generator

**Files:**
- Create: `src/polarwatch/synth.py`
- Test: `tests/test_synth.py`

This generator is the deterministic, reproducible fixture for tests and the offline demo. It emits the same raw record shape the live client produces.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_synth.py
from datetime import timezone

from polarwatch.normalize import normalize_record
from polarwatch.synth import generate_day


def test_record_count_matches_vessels_times_steps():
    records = generate_day(vessels=3, hours=1, interval_seconds=60, seed=1)
    # 1 hour / 60s = 60 steps per vessel
    assert len(records) == 3 * 60


def test_deterministic_for_same_seed():
    a = generate_day(vessels=2, hours=1, interval_seconds=300, seed=42)
    b = generate_day(vessels=2, hours=1, interval_seconds=300, seed=42)
    assert a == b


def test_records_are_normalizable_and_in_barents_region():
    records = generate_day(vessels=2, hours=1, interval_seconds=300, seed=7)
    for raw in records:
        p = normalize_record(raw)
        assert p.timestamp.tzinfo == timezone.utc
        assert 60.0 <= p.lat <= 82.0  # broad Barents/Svalbard latitude band
        assert 0.0 <= p.lon <= 40.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_synth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'polarwatch.synth'`

- [ ] **Step 3: Write the implementation**

```python
# src/polarwatch/synth.py
import math
import random
from datetime import datetime, timedelta, timezone

# A nominal start of day in the Barents Sea region.
_DEFAULT_START = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)


def generate_day(
    vessels: int = 5,
    hours: int = 24,
    interval_seconds: int = 60,
    seed: int = 0,
    start: datetime | None = None,
) -> list[dict]:
    """Generate a deterministic day of synthetic AIS records in BarentsWatch shape.

    Each vessel dead-reckons from a random start position on a fixed course and
    speed, producing one record every `interval_seconds`. Output is sorted by
    time so it is ready for the replay engine.
    """
    start = start or _DEFAULT_START
    rng = random.Random(seed)
    steps = int(hours * 3600 / interval_seconds)
    records: list[dict] = []

    for v in range(vessels):
        mmsi = 257000001 + v
        lat = 68.0 + rng.uniform(0.0, 8.0)   # 68–76 N
        lon = 12.0 + rng.uniform(0.0, 20.0)  # 12–32 E
        course = rng.uniform(0.0, 360.0)
        speed = rng.uniform(5.0, 15.0)  # knots
        name = f"SYNTH {mmsi}"

        for s in range(steps):
            t = start + timedelta(seconds=s * interval_seconds)
            # Approximate movement: 1 knot ~= 1 nm/h; 1 nm ~= 1/60 degree latitude.
            dist_nm = speed * (interval_seconds / 3600.0)
            dlat = (dist_nm / 60.0) * math.cos(math.radians(course))
            dlon = (dist_nm / 60.0) * math.sin(math.radians(course)) / max(
                math.cos(math.radians(lat)), 0.1
            )
            lat = max(60.0, min(82.0, lat + dlat))
            lon = max(0.0, min(40.0, lon + dlon))
            records.append(
                {
                    "mmsi": mmsi,
                    "latitude": round(lat, 5),
                    "longitude": round(lon, 5),
                    "speedOverGround": round(speed, 1),
                    "courseOverGround": round(course, 1),
                    "trueHeading": int(course),
                    "name": name,
                    "msgtime": t.isoformat().replace("+00:00", "Z"),
                }
            )

    records.sort(key=lambda r: r["msgtime"])
    return records
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synth.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/polarwatch/synth.py tests/test_synth.py
git commit -m "feat: add deterministic synthetic AIS day generator"
```

---

## Task 6: BarentsWatch live capture client

**Files:**
- Create: `src/polarwatch/barentswatch.py`
- Test: `tests/test_barentswatch.py`

The client is network-isolated: it accepts an `httpx.Client`, so tests drive it with `httpx.MockTransport` and never touch the network.

- [ ] **Step 1: Verify the live endpoints against current docs (real-data correctness)**

This task's logic is fully tested offline, but the live endpoint paths must be confirmed before running against real data. Check the current BarentsWatch open-AIS docs and confirm/adjust the two constants in the implementation (`TOKEN_URL`, `POSITIONS_URL`) and the auth `scope`:

Run:
```bash
# Inspect the documented token + AIS endpoints; correct the constants below if they differ.
curl -s https://www.barentswatch.no/en/articles/open-data-ais/ | head -c 4000
```
Expected: token endpoint under `id.barentswatch.no/connect/token`, AIS API under `live.ais.barentswatch.no`. If the positions path differs from `/v1/latest/combined`, update `POSITIONS_URL` to match. The offline tests below do not depend on the exact path.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_barentswatch.py
import httpx

from polarwatch.barentswatch import fetch_positions, get_token


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_get_token_returns_access_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/connect/token")
        return httpx.Response(200, json={"access_token": "tok-123", "expires_in": 3600})

    with _client(handler) as client:
        assert get_token(client, "id", "secret") == "tok-123"


def test_fetch_positions_sends_bearer_and_returns_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer tok-123"
        return httpx.Response(
            200,
            json=[
                {"mmsi": 257000001, "latitude": 70.0, "longitude": 20.0, "msgtime": "2026-06-01T00:00:00Z"}
            ],
        )

    with _client(handler) as client:
        records = fetch_positions(client, "tok-123")
    assert len(records) == 1
    assert records[0]["mmsi"] == 257000001
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_barentswatch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'polarwatch.barentswatch'`

- [ ] **Step 4: Write the implementation**

```python
# src/polarwatch/barentswatch.py
import httpx

# Confirmed in Task 6 Step 1 against current BarentsWatch open-AIS docs.
TOKEN_URL = "https://id.barentswatch.no/connect/token"
POSITIONS_URL = "https://live.ais.barentswatch.no/v1/latest/combined"
SCOPE = "ais"


def get_token(client: httpx.Client, client_id: str, client_secret: str) -> str:
    """Obtain an OAuth2 access token via the client-credentials grant."""
    response = client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": SCOPE,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def fetch_positions(client: httpx.Client, token: str) -> list[dict]:
    """Fetch the latest AIS positions. Returns raw BarentsWatch-shaped records."""
    response = client.get(POSITIONS_URL, headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return response.json()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_barentswatch.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add src/polarwatch/barentswatch.py tests/test_barentswatch.py
git commit -m "feat: add BarentsWatch AIS capture client"
```

---

## Task 7: Track builder

**Files:**
- Create: `src/polarwatch/tracks.py`
- Test: `tests/test_tracks.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tracks.py
from datetime import datetime, timezone

from polarwatch.model import AisPosition
from polarwatch.tracks import build_tracks


def _pos(mmsi, minute, name=None):
    return AisPosition(
        mmsi=mmsi,
        timestamp=datetime(2026, 6, 1, 0, minute, 0, tzinfo=timezone.utc),
        lat=70.0,
        lon=20.0,
        name=name,
    )


def test_groups_by_mmsi():
    positions = [_pos(1, 0), _pos(2, 0), _pos(1, 1)]
    tracks = build_tracks(positions)
    by_mmsi = {t.mmsi: t for t in tracks}
    assert set(by_mmsi) == {1, 2}
    assert by_mmsi[1].count == 2
    assert by_mmsi[2].count == 1


def test_positions_sorted_by_time_within_track():
    positions = [_pos(1, 5), _pos(1, 0), _pos(1, 3)]
    track = build_tracks(positions)[0]
    minutes = [p.timestamp.minute for p in track.positions]
    assert minutes == [0, 3, 5]


def test_track_name_taken_from_first_named_position():
    positions = [_pos(1, 0, name=None), _pos(1, 1, name="NORDLYS")]
    track = build_tracks(positions)[0]
    assert track.name == "NORDLYS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tracks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'polarwatch.tracks'`

- [ ] **Step 3: Write the implementation**

```python
# src/polarwatch/tracks.py
from collections import defaultdict

from polarwatch.model import AisPosition, VesselTrack


def build_tracks(positions: list[AisPosition]) -> list[VesselTrack]:
    """Group positions by MMSI into per-vessel tracks, sorted by time."""
    grouped: dict[int, list[AisPosition]] = defaultdict(list)
    for position in positions:
        grouped[position.mmsi].append(position)

    tracks: list[VesselTrack] = []
    for mmsi, group in grouped.items():
        group.sort(key=lambda p: p.timestamp)
        name = next((p.name for p in group if p.name), None)
        tracks.append(VesselTrack(mmsi=mmsi, name=name, positions=group))
    return tracks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tracks.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/polarwatch/tracks.py tests/test_tracks.py
git commit -m "feat: add per-vessel track builder"
```

---

## Task 8: Clock-driven replay engine

**Files:**
- Create: `src/polarwatch/replay.py`
- Test: `tests/test_replay.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_replay.py
from datetime import datetime, timezone

from polarwatch.model import AisPosition
from polarwatch.replay import replay


def _pos(second):
    return AisPosition(
        mmsi=1,
        timestamp=datetime(2026, 6, 1, 0, 0, second, tzinfo=timezone.utc),
        lat=70.0,
        lon=20.0,
    )


def test_emits_all_positions_in_time_order():
    positions = [_pos(30), _pos(0), _pos(10)]  # unsorted on input
    sleeps: list[float] = []
    emitted = list(replay(positions, speed=1.0, sleep=sleeps.append))
    seconds = [p.timestamp.second for p in emitted]
    assert seconds == [0, 10, 30]


def test_sleeps_scaled_by_speed():
    positions = [_pos(0), _pos(10), _pos(30)]
    sleeps: list[float] = []
    list(replay(positions, speed=10.0, sleep=sleeps.append))
    # gaps of 10s and 20s, divided by speed 10 -> 1.0s and 2.0s
    assert sleeps == [1.0, 2.0]


def test_first_position_emits_without_sleeping():
    positions = [_pos(0), _pos(5)]
    sleeps: list[float] = []
    list(replay(positions, speed=1.0, sleep=sleeps.append))
    assert len(sleeps) == 1  # only one gap, before the second position
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_replay.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'polarwatch.replay'`

- [ ] **Step 3: Write the implementation**

```python
# src/polarwatch/replay.py
import time
from typing import Callable, Iterable, Iterator

from polarwatch.model import AisPosition


def replay(
    positions: Iterable[AisPosition],
    speed: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[AisPosition]:
    """Yield positions in timestamp order, pacing emission like a live feed.

    Between consecutive positions, waits (gap_seconds / speed). The `sleep`
    callable is injectable so tests run instantly and the UI can drive its own
    clock later. `speed` > 1 plays faster than real time.
    """
    ordered = sorted(positions, key=lambda p: p.timestamp)
    previous: AisPosition | None = None
    for position in ordered:
        if previous is not None:
            gap = (position.timestamp - previous.timestamp).total_seconds() / speed
            if gap > 0:
                sleep(gap)
        previous = position
        yield position
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_replay.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/polarwatch/replay.py tests/test_replay.py
git commit -m "feat: add clock-driven replay engine"
```

---

## Task 9: CLI wiring + end-to-end pipeline test

**Files:**
- Create: `src/polarwatch/cli.py`
- Test: `tests/test_end_to_end.py`

This task ties the stages together and proves the Phase 1 done-criterion: **a Barents Sea day replays through the pipeline.**

- [ ] **Step 1: Write the failing end-to-end test**

```python
# tests/test_end_to_end.py
import json

from polarwatch.normalize import normalize_record
from polarwatch.parquet_io import (
    read_ndjson_records,
    read_positions,
    write_positions,
)
from polarwatch.replay import replay
from polarwatch.synth import generate_day
from polarwatch.tracks import build_tracks


def test_synthetic_day_replays_through_pipeline(tmp_path):
    # 1. Generate a synthetic Barents Sea day.
    records = generate_day(vessels=4, hours=2, interval_seconds=300, seed=3)
    expected_count = 4 * int(2 * 3600 / 300)
    assert len(records) == expected_count

    # 2. Capture to NDJSON (the canonical pipeline input).
    ndjson = tmp_path / "day.ndjson"
    ndjson.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    # 3. Ingest: normalize raw records -> positions -> Parquet.
    positions = [normalize_record(r) for r in read_ndjson_records(ndjson)]
    parquet = tmp_path / "day.parquet"
    write_positions(positions, parquet)

    # 4. Build tracks.
    loaded = read_positions(parquet)
    tracks = build_tracks(loaded)
    assert len(tracks) == 4

    # 5. Replay the whole day instantly (recorded sleeps, no real waiting).
    sleeps: list[float] = []
    emitted = list(replay(loaded, speed=1.0, sleep=sleeps.append))

    # Every position flows through, in non-decreasing time order.
    assert len(emitted) == expected_count
    times = [p.timestamp for p in emitted]
    assert times == sorted(times)
```

- [ ] **Step 2: Run the test to confirm the pipeline composes**

This is an integration test over modules built in Tasks 2–8, so it should PASS immediately (there is no new production code to make it go red). It verifies the stages compose correctly end-to-end.

Run: `pytest tests/test_end_to_end.py -v`
Expected: 1 passed. If it fails, fix the offending module from Tasks 2–8 before continuing.

- [ ] **Step 3: Write the CLI**

```python
# src/polarwatch/cli.py
import json
import os
from pathlib import Path

import httpx
import typer

from polarwatch.barentswatch import fetch_positions, get_token
from polarwatch.normalize import normalize_record
from polarwatch.parquet_io import read_ndjson_records, read_positions, write_positions
from polarwatch.replay import replay
from polarwatch.synth import generate_day
from polarwatch.tracks import build_tracks

app = typer.Typer(help="PolarWatch — dark vessel detection pipeline (Phase 0–1).")


def _write_ndjson(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


@app.command("synth-day")
def synth_day(
    out: Path = typer.Option(Path("data/day.ndjson"), help="Output NDJSON path."),
    vessels: int = 8,
    hours: int = 24,
    interval_seconds: int = 60,
    seed: int = 0,
) -> None:
    """Generate a deterministic synthetic Barents-Sea AIS day."""
    records = generate_day(vessels=vessels, hours=hours, interval_seconds=interval_seconds, seed=seed)
    _write_ndjson(records, out)
    typer.echo(f"Wrote {len(records)} records to {out}")


@app.command("ingest")
def ingest(
    in_path: Path = typer.Option(Path("data/day.ndjson"), "--in", help="Raw NDJSON capture."),
    out: Path = typer.Option(Path("data/day.parquet"), help="Normalized Parquet output."),
) -> None:
    """Normalize a raw AIS capture into a Parquet positions file."""
    positions = [normalize_record(r) for r in read_ndjson_records(in_path)]
    out.parent.mkdir(parents=True, exist_ok=True)
    write_positions(positions, out)
    typer.echo(f"Ingested {len(positions)} positions -> {out}")


@app.command("replay")
def replay_cmd(
    in_path: Path = typer.Option(Path("data/day.parquet"), "--in", help="Parquet positions file."),
    speed: float = typer.Option(3600.0, help="Replay speed multiplier (default: 1h/s)."),
    limit: int = typer.Option(0, help="Stop after N positions (0 = all)."),
) -> None:
    """Replay a positions file through the clock-driven engine."""
    positions = read_positions(in_path)
    tracks = build_tracks(positions)
    typer.echo(f"Replaying {len(positions)} positions across {len(tracks)} vessels (speed={speed})")
    count = 0
    for position in replay(positions, speed=speed):
        count += 1
        if limit and count >= limit:
            break
    typer.echo(f"Replayed {count} positions.")


@app.command("capture")
def capture(
    out: Path = typer.Option(Path("data/capture.ndjson"), help="Output NDJSON path."),
) -> None:
    """Capture one batch of live BarentsWatch AIS positions (needs credentials)."""
    client_id = os.environ.get("BARENTSWATCH_CLIENT_ID")
    client_secret = os.environ.get("BARENTSWATCH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise typer.BadParameter("Set BARENTSWATCH_CLIENT_ID and BARENTSWATCH_CLIENT_SECRET (.env).")
    with httpx.Client(timeout=30.0) as client:
        token = get_token(client, client_id, client_secret)
        records = fetch_positions(client, token)
    _write_ndjson(records, out)
    typer.echo(f"Captured {len(records)} live positions -> {out}")


@app.command("demo")
def demo() -> None:
    """End-to-end offline demo: synth a day, ingest, and replay it fast."""
    records = generate_day(vessels=8, hours=24, interval_seconds=300, seed=0)
    positions = [normalize_record(r) for r in records]
    tracks = build_tracks(positions)
    typer.echo(f"Demo: {len(positions)} positions across {len(tracks)} vessels.")
    count = sum(1 for _ in replay(positions, speed=1_000_000.0))
    typer.echo(f"Demo replayed {count} positions through the pipeline. OK.")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Verify the CLI runs end-to-end**

Run:
```bash
polarwatch synth-day --out data/day.ndjson --vessels 8 --hours 24 --interval-seconds 300 --seed 0
polarwatch ingest --in data/day.ndjson --out data/day.parquet
polarwatch replay --in data/day.parquet --speed 1000000
```
Expected: synth-day reports `Wrote 2304 records`, ingest reports `Ingested 2304 positions`, replay reports `Replayed 2304 positions.`

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass (model, normalize, parquet_io, synth, barentswatch, tracks, replay, end_to_end).

- [ ] **Step 6: Commit**

```bash
git add src/polarwatch/cli.py tests/test_end_to_end.py
git commit -m "feat: wire CLI and prove end-to-end day replay"
```

---

## Task 10: Docker stack + README

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `README.md`

Proves the Phase 0 done-criterion: **one command boots the stack.** Redis and PostGIS are included now as empty placeholders pre-wired for Phase 2's entity store.

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

CMD ["polarwatch", "demo"]
```

- [ ] **Step 2: Create `docker-compose.yml`**

```yaml
services:
  app:
    build: .
    env_file:
      - .env
    depends_on:
      - redis
      - postgis
    command: ["polarwatch", "demo"]

  # Phase 2 placeholders (entity store state + history). Boot empty for now.
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  postgis:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_PASSWORD: polarwatch
      POSTGRES_DB: polarwatch
    ports:
      - "5432:5432"
```

- [ ] **Step 3: Create `README.md`**

```markdown
# PolarWatch

An open-data prototype of a maritime-domain-awareness pipeline — it detects dark
and anomalous vessel behavior in the Arctic, fuses two sensor sources, and
presents them in a unified entity model and operating picture.

> **Phase 0–1 (Foundation) is implemented:** AIS ingest, per-vessel track
> building, and a clock-driven replay engine. See
> `docs/superpowers/specs/2026-06-02-polarwatch-design.md` for the full design
> and roadmap (entity store, detection, fusion, and the operator UI follow).

## Quickstart (local)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest                      # run the test suite

# Offline end-to-end demo (no credentials needed):
polarwatch synth-day --out data/day.ndjson
polarwatch ingest    --in  data/day.ndjson --out data/day.parquet
polarwatch replay    --in  data/day.parquet --speed 3600
```

## Live data (optional)

Register a client for Norway's BarentsWatch open AIS API, copy `.env.example`
to `.env`, fill in the credentials, then:

```bash
polarwatch capture --out data/capture.ndjson
polarwatch ingest  --in  data/capture.ndjson --out data/capture.parquet
polarwatch replay  --in  data/capture.parquet
```

## Run the stack

```bash
docker compose up --build
```

Boots the app (runs the offline demo) plus Redis and PostGIS (placeholders for
the Phase 2 entity store).

## Pipeline (Phase 0–1)

```
synth-day / capture   raw AIS (NDJSON, BarentsWatch shape)
        │
        ▼  normalize
   positions (Parquet)
        │
        ├─ build_tracks ─▶ per-vessel VesselTrack
        ▼
   replay (clock-driven, speed-controlled)
```
```

- [ ] **Step 4: Verify the stack boots**

Run: `docker compose up --build`
Expected: `redis` and `postgis` start; `app` builds, runs the demo, and logs `Demo replayed ... positions through the pipeline. OK.` (Press Ctrl-C to stop; `docker compose down` to clean up.)

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml README.md
git commit -m "feat: add Docker stack and project README"
```

---

## Self-Review Notes

**Spec coverage (Phase 0–1 scope only):**
- Phase 0 "Repo, Docker Compose, data keys, README skeleton; one command boots the empty stack" → Tasks 1, 10 (+ `.env.example` data keys in Task 1). ✅
- Phase 1 "AIS ingest" → Tasks 3, 4, 6. ✅
- Phase 1 "track builder" → Task 7. ✅
- Phase 1 "clock-driven replay" → Task 8. ✅
- Phase 1 done-criterion "a Barents Sea day replays through the pipeline" → Task 9 end-to-end test + CLI run. ✅
- Spec §4 "normalize to a common schema" → Tasks 2, 3. ✅
- Spec data strategy "Kystverket/BarentsWatch primary AIS" → Task 6 (live), Task 5 (synthetic reproducible fixture). ✅

**Intentionally deferred (later phases, not Phase 0–1):** entity store/gRPC-REST service (Phase 2), detection rules (Phase 3), UI (Phase 4), fusion + second sensor (Phase 5), ML + eval harness (Phase 6), GeoParquet/geopandas spatial features. These are explicitly out of scope here.

**Type consistency:** `AisPosition`/`VesselTrack` fields, `normalize_record`, `generate_day(vessels, hours, interval_seconds, seed)`, `build_tracks`, and `replay(positions, speed, sleep)` signatures are used identically across Tasks 2–9 and the CLI. ✅

**Open verification item:** Task 6 Step 1 — confirm the live BarentsWatch `POSITIONS_URL` against current docs before capturing real data. All other logic is tested offline and does not depend on it.
```
