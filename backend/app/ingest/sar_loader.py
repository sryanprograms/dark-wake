"""Load GFW SAR detections into PostGIS and cluster into scenes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import psycopg2
from psycopg2.extras import execute_values

from app.config.thresholds import SCENE_CLUSTER_WINDOW_S
from app.ingest.loader import connect as _connect


def connect(database_url: str):
    return _connect(database_url)


def _parse_t(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _should_merge(
    left_scene_id: str | None,
    left_t: datetime,
    right_scene_id: str | None,
    right_t: datetime,
    *,
    window_s: int = SCENE_CLUSTER_WINDOW_S,
) -> bool:
    if left_scene_id and right_scene_id and left_scene_id == right_scene_id:
        return True
    return abs((right_t - left_t).total_seconds()) <= window_s


def cluster_detections_into_scenes(
    detections: list[dict[str, Any]],
    *,
    window_s: int = SCENE_CLUSTER_WINDOW_S,
) -> list[dict[str, Any]]:
    """Group detections into scenes by shared scene_id or time window."""
    if not detections:
        return []

    parsed: list[dict[str, Any]] = []
    for det in detections:
        parsed.append(
            {
                **det,
                "t_dt": _parse_t(det["t"]),
                "scene_id_raw": det.get("scene_id") or det.get("sceneId"),
            }
        )
    parsed.sort(key=lambda row: row["t_dt"])

    n = len(parsed)
    parent = list(range(n))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for i in range(n):
        for j in range(i + 1, n):
            if _should_merge(
                parsed[i]["scene_id_raw"],
                parsed[i]["t_dt"],
                parsed[j]["scene_id_raw"],
                parsed[j]["t_dt"],
                window_s=window_s,
            ):
                union(i, j)

    groups: dict[int, list[dict[str, Any]]] = {}
    for index, row in enumerate(parsed):
        groups.setdefault(find(index), []).append(row)

    scenes: list[dict[str, Any]] = []
    for group in groups.values():
        group.sort(key=lambda row: row["t_dt"])
        scene_ids = [row["scene_id_raw"] for row in group if row["scene_id_raw"]]
        scene_id = scene_ids[0] if scene_ids else f"synthetic-{group[0]['t_dt'].isoformat()}"
        scenes.append(
            {
                "scene_id": scene_id,
                "t": group[0]["t_dt"],
                "detections": group,
                "detection_count": len(group),
            }
        )

    scenes.sort(key=lambda scene: scene["t"])
    return _merge_scenes_by_timestamp(scenes)


def _merge_scenes_by_timestamp(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse scenes that share the same timestamp (sar_scene.t is UNIQUE)."""
    merged: dict[datetime, dict[str, Any]] = {}
    for scene in scenes:
        key = scene["t"]
        if key not in merged:
            merged[key] = {
                "scene_id": scene["scene_id"],
                "t": scene["t"],
                "detections": list(scene["detections"]),
                "detection_count": scene["detection_count"],
            }
            continue
        existing = merged[key]
        existing["detections"].extend(scene["detections"])
        existing["detection_count"] = len(existing["detections"])
        if existing["scene_id"].startswith("synthetic-") and not scene["scene_id"].startswith(
            "synthetic-"
        ):
            existing["scene_id"] = scene["scene_id"]
    return sorted(merged.values(), key=lambda scene: scene["t"])


def _detection_raw(det: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in det.items()
        if key not in {"t_dt", "scene_id_raw"}
    }


def _dedupe_detections(detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse duplicate GFW rows that share the same instant and position."""
    seen: dict[tuple[str, float, float], dict[str, Any]] = {}
    for det in detections:
        t = _parse_t(det["t"]).isoformat()
        lon = round(float(det["lon"]), 6)
        lat = round(float(det["lat"]), 6)
        seen[(t, lon, lat)] = det
    return list(seen.values())


def _dedupe_scene_rows(
    rows: list[tuple[str, datetime, int]],
) -> list[tuple[str, datetime, int]]:
    """One sar_scene row per timestamp (table has UNIQUE on t)."""
    merged: dict[datetime, tuple[str, datetime, int]] = {}
    for scene_id, t, count in rows:
        if t not in merged:
            merged[t] = (scene_id, t, count)
            continue
        prev_id, prev_t, prev_count = merged[t]
        keep_id = prev_id if not prev_id.startswith("synthetic-") else scene_id
        merged[t] = (keep_id, t, prev_count + count)
    return list(merged.values())


def _dedupe_detection_rows(rows: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """One row per (source, t, lon, lat) for ON CONFLICT upserts."""
    seen: dict[tuple[Any, ...], tuple[Any, ...]] = {}
    for row in rows:
        source, _scene_id, t, lon, lat = row[0], row[1], row[2], row[3], row[4]
        key = (source, t, round(float(lon), 6), round(float(lat), 6))
        seen[key] = row
    return list(seen.values())


def purge_sar_outside_bbox(conn, bbox: dict[str, float]) -> dict[str, int]:
    """Remove SAR scenes/detections outside the configured AOI bbox."""
    envelope = (
        "ST_MakeEnvelope(%(min_lon)s, %(min_lat)s, %(max_lon)s, %(max_lat)s, 4326)"
    )
    with conn.cursor() as cur:
        cur.execute(
            f"""
            DELETE FROM contact
            WHERE sar_detection_id IN (
                SELECT id FROM sar_detection
                WHERE NOT ST_Within(geom, {envelope})
            )
            """,
            bbox,
        )
        contacts_removed = cur.rowcount
        cur.execute(
            f"""
            DELETE FROM sar_detection
            WHERE NOT ST_Within(geom, {envelope})
            """,
            bbox,
        )
        detections_removed = cur.rowcount
        cur.execute(
            """
            DELETE FROM sar_scene s
            WHERE NOT EXISTS (
                SELECT 1 FROM sar_detection d WHERE d.scene_id = s.scene_id
            )
            """
        )
        scenes_removed = cur.rowcount
        cur.execute(
            """
            UPDATE sar_scene s
            SET detection_count = sub.cnt
            FROM (
                SELECT scene_id, COUNT(*)::int AS cnt
                FROM sar_detection
                GROUP BY scene_id
            ) sub
            WHERE s.scene_id = sub.scene_id
            """
        )
    conn.commit()
    return {
        "contacts": contacts_removed,
        "detections": detections_removed,
        "scenes": scenes_removed,
    }


def load_sar_detections(
    conn,
    detections: list[dict[str, Any]],
    *,
    clear_existing: bool = False,
    source: str = "gfw",
) -> dict[str, int]:
    """Cluster detections into scenes and upsert into PostGIS."""
    if clear_existing:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE contact, sar_detection, sar_scene RESTART IDENTITY CASCADE"
            )
        conn.commit()

    detections = _dedupe_detections(detections)
    scenes = cluster_detections_into_scenes(detections)
    scene_rows: list[tuple[str, datetime, int]] = []
    detection_rows: list[tuple[Any, ...]] = []

    for scene in scenes:
        scene_rows.append((scene["scene_id"], scene["t"], scene["detection_count"]))
        for det in scene["detections"]:
            detection_rows.append(
                (
                    source,
                    scene["scene_id"],
                    det["t_dt"],
                    float(det["lon"]),
                    float(det["lat"]),
                    det.get("length_m"),
                    det.get("confidence"),
                    psycopg2.extras.Json(_detection_raw(det)),
                )
            )

    scene_rows = _dedupe_scene_rows(scene_rows)
    detection_rows = _dedupe_detection_rows(detection_rows)

    with conn.cursor() as cur:
        if scene_rows:
            execute_values(
                cur,
                """
                INSERT INTO sar_scene (scene_id, t, detection_count)
                VALUES %s
                ON CONFLICT (t) DO UPDATE SET
                    scene_id = EXCLUDED.scene_id,
                    detection_count = EXCLUDED.detection_count
                """,
                scene_rows,
                template="(%s, %s, %s)",
            )

        if detection_rows:
            execute_values(
                cur,
                """
                INSERT INTO sar_detection (
                    source, scene_id, t, geom, length_m, confidence, raw
                )
                VALUES %s
                ON CONFLICT (source, t, (ST_X(geom)), (ST_Y(geom))) DO UPDATE SET
                    scene_id = EXCLUDED.scene_id,
                    length_m = EXCLUDED.length_m,
                    confidence = EXCLUDED.confidence,
                    raw = EXCLUDED.raw
                """,
                detection_rows,
                template=(
                    "(%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)"
                ),
            )

    conn.commit()
    return {
        "scenes": len(scenes),
        "detections": len(detection_rows),
    }
