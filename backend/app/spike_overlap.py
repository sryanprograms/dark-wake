"""Phase 0 overlap gate — confirm AIS and SAR data overlap for the AOI/window."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config.thresholds import OVERLAP_MIN_AIS_POSITIONS, OVERLAP_TIME_MARGIN_S


@dataclass
class OverlapReport:
    overlap: bool
    bbox: dict[str, float]
    ais_source: str
    ais_count: int
    ais_start: str | None
    ais_end: str | None
    sar_count: int
    sar_scene_times: list[str]
    overlapping_scene_time: str | None
    ais_positions_at_scene: int
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overlap": self.overlap,
            "bbox": self.bbox,
            "ais_source": self.ais_source,
            "ais_count": self.ais_count,
            "ais_time_range": [self.ais_start, self.ais_end],
            "sar_count": self.sar_count,
            "sar_scene_times": self.sar_scene_times,
            "overlapping_scene_time": self.overlapping_scene_time,
            "ais_positions_at_scene": self.ais_positions_at_scene,
            "reasons": self.reasons,
        }


def _parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _scene_times(sar_detections: list[dict[str, Any]]) -> list[datetime]:
    times = {_parse_time(d["t"]) for d in sar_detections}
    return sorted(times)


def _ais_window(ais_positions: list[dict[str, Any]]) -> tuple[datetime | None, datetime | None]:
    if not ais_positions:
        return None, None
    times = [_parse_time(p["t"]) for p in ais_positions]
    return min(times), max(times)


def _positions_near_time(
    ais_positions: list[dict[str, Any]],
    scene_time: datetime,
    margin_s: int,
) -> list[dict[str, Any]]:
    lo = scene_time - timedelta(seconds=margin_s)
    hi = scene_time + timedelta(seconds=margin_s)
    return [p for p in ais_positions if lo <= _parse_time(p["t"]) <= hi]


def check_overlap(
    *,
    bbox: dict[str, float],
    ais_positions: list[dict[str, Any]],
    sar_detections: list[dict[str, Any]],
    ais_source: str,
    time_margin_s: int = OVERLAP_TIME_MARGIN_S,
    min_ais_positions: int = OVERLAP_MIN_AIS_POSITIONS,
) -> OverlapReport:
    reasons: list[str] = []
    ais_start, ais_end = _ais_window(ais_positions)
    scene_dt_list = _scene_times(sar_detections)

    if not sar_detections:
        reasons.append("No SAR detections inside the AOI bbox.")
    if not ais_positions:
        reasons.append("No AIS positions inside the AOI/time window.")

    overlapping_scene: datetime | None = None
    ais_at_scene = 0

    if ais_start and ais_end and scene_dt_list:
        margin = timedelta(seconds=time_margin_s)
        for scene_time in scene_dt_list:
            if (ais_start - margin) <= scene_time <= (ais_end + margin):
                near = _positions_near_time(ais_positions, scene_time, time_margin_s)
                if len(near) >= min_ais_positions:
                    overlapping_scene = scene_time
                    ais_at_scene = len(near)
                    break
                reasons.append(
                    f"SAR scene {scene_time.isoformat()} is in AIS window but only "
                    f"{len(near)} AIS positions within ±{time_margin_s}s "
                    f"(need {min_ais_positions})."
                )
        if overlapping_scene is None and not any(
            "SAR scene" in r for r in reasons
        ):
            reasons.append(
                "No SAR scene timestamp falls within the AIS coverage window "
                f"(±{time_margin_s}s margin)."
            )

    overlap = overlapping_scene is not None and bool(sar_detections)

    return OverlapReport(
        overlap=overlap,
        bbox=bbox,
        ais_source=ais_source,
        ais_count=len(ais_positions),
        ais_start=ais_start.isoformat() if ais_start else None,
        ais_end=ais_end.isoformat() if ais_end else None,
        sar_count=len(sar_detections),
        sar_scene_times=[t.isoformat() for t in scene_dt_list],
        overlapping_scene_time=overlapping_scene.isoformat() if overlapping_scene else None,
        ais_positions_at_scene=ais_at_scene,
        reasons=reasons,
    )


def format_report(report: OverlapReport) -> str:
    lines = [
        "=" * 60,
        "DarkWake Phase 0 — AIS/SAR Overlap Spike",
        "=" * 60,
        f"AOI bbox: lat [{report.bbox['min_lat']}, {report.bbox['max_lat']}], "
        f"lon [{report.bbox['min_lon']}, {report.bbox['max_lon']}]",
        f"AIS source: {report.ais_source}",
        f"AIS positions in AOI/window: {report.ais_count}",
        f"AIS time range: {report.ais_start} → {report.ais_end}",
        f"SAR detections in AOI: {report.sar_count}",
        f"SAR scene times ({len(report.sar_scene_times)}): "
        + (", ".join(report.sar_scene_times[:5]) if report.sar_scene_times else "none"),
    ]
    if len(report.sar_scene_times) > 5:
        lines.append(f"  … and {len(report.sar_scene_times) - 5} more")

    if report.overlapping_scene_time:
        lines.append(
            f"Overlapping scene: {report.overlapping_scene_time} "
            f"({report.ais_positions_at_scene} AIS positions within margin)"
        )

    status = "PASS" if report.overlap else "FAIL"
    lines.append(f"\nResult: {status}")
    if report.reasons:
        lines.append("Notes:")
        for reason in report.reasons:
            lines.append(f"  - {reason}")
    lines.append("=" * 60)
    return "\n".join(lines)
