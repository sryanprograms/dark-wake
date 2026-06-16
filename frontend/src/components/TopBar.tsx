import { Activity, Radio } from "lucide-react";
import { formatUtcShort } from "../utils/time";

type AppMode = "live" | "replay";

type TopBarProps = {
  connected: boolean;
  playing: boolean;
  current: string;
  scenarioName?: string;
  vesselCount: number;
  trackCount: number;
  positionCount: number | null;
  isLive: boolean;
  mode: AppMode;
  aisConnected?: boolean;
  onModeChange: (mode: AppMode) => void;
};

function KpiChip({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="kpi-chip">
      <span className="kpi-chip__label">{label}</span>
      <span className="kpi-chip__value">{value}</span>
    </div>
  );
}

export function TopBar({
  connected,
  playing,
  current,
  scenarioName = "Gulf of Finland corridor",
  vesselCount,
  trackCount,
  positionCount,
  isLive,
  mode,
  aisConnected = false,
  onModeChange,
}: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="top-bar__brand">
        <div className="top-bar__title-row">
          <h1>DarkWake</h1>
          <span className="top-bar__mission">{scenarioName}</span>
        </div>
        <div className="top-bar__subtitle">AIS + SAR maritime situational awareness</div>
      </div>

      <div className="top-bar__mode-toggle">
        <button
          type="button"
          className={`mode-toggle${mode === "live" ? " mode-toggle--active" : ""}`}
          onClick={() => onModeChange("live")}
        >
          Live
        </button>
        <button
          type="button"
          className={`mode-toggle${mode === "replay" ? " mode-toggle--active" : ""}`}
          onClick={() => onModeChange("replay")}
        >
          Replay
        </button>
      </div>

      <div className="top-bar__clock">
        <span className="top-bar__clock-label">{mode === "live" ? "UTC" : "Scenario time"}</span>
        <time className="top-bar__clock-value">{current ? formatUtcShort(current) : "—"}</time>
      </div>

      <div className="top-bar__stats">
        <KpiChip label="Contacts" value={connected ? vesselCount : "—"} />
        <KpiChip label="Tracks" value={connected ? trackCount : "—"} />
        <KpiChip label="Positions" value={connected ? (positionCount ?? "—") : "—"} />
      </div>

      <div className="top-bar__status">
        <span className={`status-dot ${connected ? "status-dot--live" : "status-dot--offline"}`} />
        <span className="status-text">{connected ? "Connected" : "Connecting…"}</span>
        {connected && mode === "live" && aisConnected && (
          <span className="live-badge">
            <Radio size={12} />
            LIVE
          </span>
        )}
        {connected && mode === "replay" && playing && !isLive && (
          <span className="replay-badge">
            <Activity size={12} />
            REPLAY
          </span>
        )}
      </div>
    </header>
  );
}
