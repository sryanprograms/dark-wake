import { Activity, Radio } from "lucide-react";
import { formatStoredCount, formatTimelineSpan } from "../utils/timelineCoverage";
import { formatUtcShort } from "../utils/time";
import type { PlayheadMode } from "../ws/timeline";

type TopBarProps = {
  connected: boolean;
  current: string;
  scenarioName?: string;
  dataStart: string;
  liveEdge: string;
  vesselCount: number;
  attentionCount: number;
  trackCount: number;
  positionCount: number | null;
  sceneCount: number | null;
  playheadMode: PlayheadMode;
  aisConnected?: boolean;
  aisReceiving?: boolean;
};

function KpiChip({
  label,
  value,
  title,
  variant,
}: {
  label: string;
  value: string | number;
  title?: string;
  variant?: "default" | "attention";
}) {
  return (
    <div
      className={`kpi-chip${variant === "attention" ? " kpi-chip--attention" : ""}`}
      title={title}
    >
      <span className="kpi-chip__label">{label}</span>
      <span className="kpi-chip__value">{value}</span>
    </div>
  );
}

function modeContext(mode: PlayheadMode): string {
  if (mode === "live") return "Monitoring at live edge";
  if (mode === "scene") return "SAR scene fusion";
  return "Reviewing historical data";
}

function connectionLabel(
  connected: boolean,
  mode: PlayheadMode,
  aisConnected: boolean,
  aisReceiving: boolean,
): string {
  if (!connected) return "Connecting…";
  if (mode === "live") {
    if (!aisConnected) return "Ship data unavailable";
    if (!aisReceiving) return "Awaiting live vessel data";
    return "Live feed active";
  }
  if (mode === "scene") return "Scene fusion active";
  return "Historical playback";
}

function modeBadge(mode: PlayheadMode) {
  if (mode === "live") {
    return (
      <span className="live-badge">
        <Radio size={12} />
        LIVE
      </span>
    );
  }
  if (mode === "scene") {
    return (
      <span className="scene-badge">
        <Activity size={12} />
        SAR SCENE
      </span>
    );
  }
  return (
    <span className="replay-badge">
      <Activity size={12} />
      HISTORICAL
    </span>
  );
}

export function TopBar({
  connected,
  current,
  scenarioName = "Danish Belt",
  dataStart,
  liveEdge,
  vesselCount,
  attentionCount,
  trackCount,
  positionCount,
  sceneCount,
  playheadMode,
  aisConnected = false,
  aisReceiving = false,
}: TopBarProps) {
  const spanLabel = formatTimelineSpan(dataStart, liveEdge);
  const coverageValue =
    connected && positionCount != null
      ? `${spanLabel} · ${formatStoredCount(positionCount)}`
      : "—";
  const coverageTooltip =
    connected && positionCount != null
      ? [
          `${spanLabel} of stored AIS history`,
          `${positionCount.toLocaleString()} positions`,
          sceneCount != null ? `${sceneCount.toLocaleString()} SAR scenes` : null,
          `${trackCount} track histories on map`,
        ]
          .filter(Boolean)
          .join(" · ")
      : undefined;
  const vesselTooltip =
    connected && positionCount != null
      ? `${trackCount} visible track histories · ${positionCount.toLocaleString()} stored positions`
      : undefined;

  return (
    <header className="top-bar">
      <div className="top-bar__brand">
        <div className="top-bar__title-row">
          <h1>DarkWake</h1>
          <span className="top-bar__mission">{scenarioName}</span>
        </div>
        <div className="top-bar__subtitle">{modeContext(playheadMode)} · Ship reports and radar</div>
      </div>

      <div className="top-bar__clock">
        <span className="top-bar__clock-label">
          {playheadMode === "live" ? "Live time" : "Playhead time"}
        </span>
        <time className="top-bar__clock-value">{current ? formatUtcShort(current) : "—"}</time>
      </div>

      <div className="top-bar__stats">
        <KpiChip
          label="Coverage"
          value={coverageValue}
          title={coverageTooltip}
        />
        <KpiChip
          label="Vessels"
          value={connected ? vesselCount : "—"}
          title={vesselTooltip}
        />
        {connected && attentionCount > 0 ? (
          <KpiChip
            label="Need attention"
            value={attentionCount}
            variant="attention"
          />
        ) : null}
      </div>

      <div className="top-bar__status">
        <span
          className={`status-dot ${connected ? (playheadMode === "live" && aisConnected ? "status-dot--live" : "status-dot--ready") : "status-dot--offline"}`}
        />
        <span className="status-text">
          {connectionLabel(connected, playheadMode, aisConnected, aisReceiving)}
        </span>
        {connected && modeBadge(playheadMode)}
      </div>
    </header>
  );
}
