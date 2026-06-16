"""Live AIS silence precursors (Tier 0) — not confirmed dark ships."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config.thresholds import GAP_HIGH_S, GAP_MIN_S
from app.live.registry import VesselState


def _gap_tier_and_severity(gap_s: float, *, ongoing: bool) -> tuple[str, str]:
    """Return (tier, severity). tier is watch or suspicious; not a dark-ship verdict."""
    if gap_s >= GAP_HIGH_S:
        return "suspicious", "high"
    if ongoing:
        return "watch", "medium"
    return "watch", "medium"


def detect_ais_gap_resume(
    state: VesselState,
    *,
    previous_at: datetime | None,
    current_at: datetime,
    source: str = "digitraffic",
) -> dict[str, Any] | None:
    """Emit when a monitored vessel resumes after a ground-truth silence window."""
    if not state.gap_monitor or previous_at is None:
        return None

    gap_s = (current_at - previous_at).total_seconds()
    if gap_s < GAP_MIN_S:
        return None

    if state.last_gap_alert_at and state.last_gap_alert_at >= previous_at:
        return None

    state.last_gap_alert_at = current_at
    gap_min = int(gap_s // 60)
    tier, severity = _gap_tier_and_severity(gap_s, ongoing=False)
    name = state.name or f"MMSI {state.mmsi}"
    return {
        "kind": "ais_gap_resume",
        "tier": tier,
        "severity": severity,
        "mmsi": state.mmsi,
        "t": current_at.astimezone(timezone.utc).isoformat(),
        "title": f"{name} — AIS gap resumed ({gap_min} min)",
        "reason": (
            f"Vessel resumed reporting after {gap_min} minutes of silence "
            f"({source}, threshold {GAP_MIN_S // 60} min). "
            "Precursor only — not a confirmed dark ship."
        ),
        "details": {
            "tier": tier,
            "source": source,
            "gap_seconds": int(gap_s),
            "gap_start": previous_at.astimezone(timezone.utc).isoformat(),
            "gap_end": current_at.astimezone(timezone.utc).isoformat(),
        },
        "lat": state.latest.lat if state.latest else None,
        "lon": state.latest.lon if state.latest else None,
    }


def detect_ais_silent(
    state: VesselState,
    *,
    now: datetime,
    source: str = "digitraffic",
) -> dict[str, Any] | None:
    """Emit when a monitored vessel stops appearing in the ground-truth feed."""
    if not state.gap_monitor or state.last_ingest_at is None:
        return None

    gap_s = (now - state.last_ingest_at).total_seconds()
    if gap_s < GAP_MIN_S:
        return None

    if state.last_gap_alert_at and state.last_gap_alert_at >= state.last_ingest_at:
        return None

    state.last_gap_alert_at = now
    gap_min = int(gap_s // 60)
    tier, severity = _gap_tier_and_severity(gap_s, ongoing=True)
    name = state.name or f"MMSI {state.mmsi}"
    return {
        "kind": "ais_silent",
        "tier": tier,
        "severity": severity,
        "mmsi": state.mmsi,
        "t": now.astimezone(timezone.utc).isoformat(),
        "title": f"{name} — AIS silent ({gap_min} min)",
        "reason": (
            f"No {source} reports for {gap_min} minutes "
            f"(threshold {GAP_MIN_S // 60} min). "
            "Precursor only — not a confirmed dark ship."
        ),
        "details": {
            "tier": tier,
            "source": source,
            "gap_seconds": int(gap_s),
            "last_seen": state.last_ingest_at.astimezone(timezone.utc).isoformat(),
        },
        "lat": state.latest.lat if state.latest else None,
        "lon": state.latest.lon if state.latest else None,
    }
