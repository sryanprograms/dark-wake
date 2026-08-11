import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Anchor, ChevronDown, Crosshair } from "lucide-react";
import type { VesselPoint } from "../map/MapView";
import { alertKindLabel, alertTierLabel, isAttentionAlert } from "../utils/alerts";
import { isVesselMoving } from "../utils/vesselFilters";
import { formatLastReportLong, formatUtcShort } from "../utils/time";
import type { AlertEvent } from "../ws/timeline";
import { CollapsiblePanel } from "./CollapsiblePanel";

type VesselDetailProps = {
  vessel: VesselPoint | null;
  alerts?: AlertEvent[];
  onCenter?: () => void;
  onCollapsedChange?: (collapsed: boolean) => void;
  referenceTime?: string;
};

function alertSeverityClass(severity: string): string {
  if (severity === "high") return "detail-panel__alert--high";
  if (severity === "medium") return "detail-panel__alert--medium";
  return "detail-panel__alert--low";
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-row">
      <span className="detail-row__label">{label}</span>
      <span className="detail-row__value">{value}</span>
    </div>
  );
}

function vesselSubtitle(vessel: VesselPoint): string {
  const parts: string[] = [];
  const flag = vessel.country ?? vessel.flag;
  if (flag) parts.push(`${flag}-flagged`);
  if (vessel.ship_type) parts.push(vessel.ship_type.toLowerCase());
  const moving = isVesselMoving(vessel);
  if (vessel.sog != null) {
    parts.push(`${moving ? "underway" : "stopped"} at ${vessel.sog.toFixed(1)} kn`);
  } else {
    parts.push(moving ? "underway" : "stopped");
  }
  return parts.join(" · ");
}

export function VesselDetail({ vessel, alerts = [], onCenter, onCollapsedChange, referenceTime }: VesselDetailProps) {
  const [collapsed, setCollapsed] = useState(!vessel);

  const vesselAlerts = useMemo(() => {
    if (!vessel) return [];
    return alerts.filter((alert) => alert.mmsi === vessel.mmsi && isAttentionAlert(alert));
  }, [alerts, vessel]);

  const primaryAlert = vesselAlerts[0];

  useEffect(() => {
    if (vessel) {
      setCollapsed(false);
      onCollapsedChange?.(false);
    }
  }, [vessel?.mmsi, onCollapsedChange]);

  const handleCollapsedChange = (next: boolean) => {
    setCollapsed(next);
    onCollapsedChange?.(next);
  };

  const headerActions =
    vessel && onCenter ? (
      <button type="button" className="detail-panel__center" onClick={onCenter}>
        Center map
      </button>
    ) : undefined;

  return (
    <CollapsiblePanel
      className="detail-panel"
      title="Selected vessel"
      icon={<Crosshair size={14} />}
      edge="right"
      collapsed={collapsed}
      onCollapsedChange={handleCollapsedChange}
      headerActions={headerActions}
    >
      {!vessel ? (
        <div className="detail-panel__placeholder">
          <Anchor size={28} strokeWidth={1.25} />
          <p>Select a vessel on the map or from the list to see details and any alerts.</p>
        </div>
      ) : (
        <>
          {(() => {
            const moving = isVesselMoving(vessel);
            const name = vessel.name?.trim() || `Vessel ${vessel.mmsi}`;

            return (
              <>
                <div className="detail-panel__title">
                  <h2>{name}</h2>
                  <p className="detail-panel__subtitle">{vesselSubtitle(vessel)}</p>
                  <span
                    className={`contact-badge ${moving ? "contact-badge--moving" : "contact-badge--idle"}`}
                  >
                    {moving ? "Underway" : "Stopped"}
                  </span>
                </div>

                {primaryAlert ? (
                  <div className="detail-panel__insight">
                    <div className="detail-panel__insight-header">
                      <AlertTriangle size={14} />
                      <span>Why this matters</span>
                    </div>
                    <p className="detail-panel__insight-reason">
                      {primaryAlert.reason || primaryAlert.title}
                    </p>
                    <div className="detail-panel__insight-meta">
                      <span>{alertKindLabel(primaryAlert.kind)}</span>
                      {alertTierLabel(primaryAlert.tier) ? (
                        <span>{alertTierLabel(primaryAlert.tier)}</span>
                      ) : null}
                      <span>{formatUtcShort(primaryAlert.t)}</span>
                    </div>
                  </div>
                ) : null}

                <details className="detail-panel__details" open>
                  <summary className="detail-panel__details-summary">
                    Vessel details
                    <ChevronDown size={14} className="detail-panel__details-chevron" aria-hidden />
                  </summary>
                  <div className="detail-panel__section">
                    <DetailRow label="MMSI" value={String(vessel.mmsi)} />
                    <DetailRow label="Nation" value={vessel.country ?? vessel.flag ?? "—"} />
                    <DetailRow label="Ship type" value={vessel.ship_type ?? "—"} />
                    <DetailRow label="Latitude" value={vessel.lat.toFixed(5)} />
                    <DetailRow label="Longitude" value={vessel.lon.toFixed(5)} />
                    <DetailRow
                      label="Speed (SOG)"
                      value={vessel.sog != null ? `${vessel.sog.toFixed(1)} kn` : "—"}
                    />
                    <DetailRow
                      label="Course (COG)"
                      value={vessel.cog != null ? `${vessel.cog.toFixed(0)}°` : "—"}
                    />
                    <DetailRow
                      label="Heading"
                      value={
                        vessel.heading != null && vessel.heading !== 511
                          ? `${vessel.heading.toFixed(0)}°`
                          : "—"
                      }
                    />
                    <DetailRow
                      label="Last report"
                      value={vessel.t ? formatLastReportLong(vessel.t, referenceTime) : "—"}
                    />
                  </div>
                </details>

                {vesselAlerts.length > 0 ? (
                  <div className="detail-panel__alerts">
                    <div className="detail-panel__alerts-header">
                      <AlertTriangle size={14} />
                      <span>All alerts</span>
                      <span className="detail-panel__alerts-count">{vesselAlerts.length}</span>
                    </div>
                    <ul className="detail-panel__alert-list">
                      {vesselAlerts.map((alert, index) => (
                        <li
                          key={`${alert.id ?? alert.t}-${index}`}
                          className={`detail-panel__alert ${alertSeverityClass(alert.severity)}`}
                        >
                          <div className="detail-panel__alert-title">{alert.title}</div>
                          <div className="detail-panel__alert-meta">
                            {formatUtcShort(alert.t)} · {alertKindLabel(alert.kind)}
                          </div>
                          {alert.reason ? (
                            <div className="detail-panel__alert-reason">{alert.reason}</div>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="detail-panel__alerts-empty">No alerts for this vessel.</p>
                )}
              </>
            );
          })()}
        </>
      )}
    </CollapsiblePanel>
  );
}
