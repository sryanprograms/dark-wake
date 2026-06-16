import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Anchor, Crosshair } from "lucide-react";
import type { VesselPoint } from "../map/MapView";
import { formatUtc, formatUtcShort } from "../utils/time";
import type { AlertEvent } from "../ws/live";
import { CollapsiblePanel } from "./CollapsiblePanel";

type VesselDetailProps = {
  vessel: VesselPoint | null;
  alerts?: AlertEvent[];
  onCenter?: () => void;
  onCollapsedChange?: (collapsed: boolean) => void;
};

function isAisSilenceAlert(alert: AlertEvent): boolean {
  return (
    alert.kind === "ais_silent" ||
    alert.kind === "ais_gap_resume" ||
    alert.kind === "ais_gap"
  );
}

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

export function VesselDetail({ vessel, alerts = [], onCenter, onCollapsedChange }: VesselDetailProps) {
  const [collapsed, setCollapsed] = useState(!vessel);

  const vesselAlerts = useMemo(() => {
    if (!vessel) return [];
    return alerts.filter((alert) => alert.mmsi === vessel.mmsi && isAisSilenceAlert(alert));
  }, [alerts, vessel]);

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
        Center
      </button>
    ) : undefined;

  return (
    <CollapsiblePanel
      className="detail-panel"
      title="Contact detail"
      icon={<Crosshair size={14} />}
      edge="right"
      collapsed={collapsed}
      onCollapsedChange={handleCollapsedChange}
      headerActions={headerActions}
    >
      {!vessel ? (
        <div className="detail-panel__placeholder">
          <Anchor size={28} strokeWidth={1.25} />
          <p>Select a contact from the map or fleet list to inspect.</p>
        </div>
      ) : (
        <>
          {(() => {
            const moving = vessel.sog != null && vessel.sog > 0.5;
            const name = vessel.name?.trim() || `MMSI ${vessel.mmsi}`;

            return (
              <>
                <div className="detail-panel__title">
                  <h2>{name}</h2>
                  <span
                    className={`contact-badge ${moving ? "contact-badge--moving" : "contact-badge--idle"}`}
                  >
                    {moving ? "Underway" : "Stationary"}
                  </span>
                </div>

                <div className="detail-panel__section">
                  <DetailRow label="MMSI" value={String(vessel.mmsi)} />
                  <DetailRow label="Flag" value={vessel.country ?? vessel.flag ?? "—"} />
                  <DetailRow label="Ship type" value={vessel.ship_type ?? "—"} />
                  <DetailRow label="Latitude" value={vessel.lat.toFixed(5)} />
                  <DetailRow label="Longitude" value={vessel.lon.toFixed(5)} />
                  <DetailRow
                    label="SOG"
                    value={vessel.sog != null ? `${vessel.sog.toFixed(1)} kn` : "—"}
                  />
                  <DetailRow
                    label="COG"
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
                  <DetailRow label="Last report" value={vessel.t ? formatUtc(vessel.t) : "—"} />
                </div>

                <div className="detail-panel__alerts">
                  <div className="detail-panel__alerts-header">
                    <AlertTriangle size={14} />
                    <span>Alerts</span>
                    {vesselAlerts.length > 0 ? (
                      <span className="detail-panel__alerts-count">{vesselAlerts.length}</span>
                    ) : null}
                  </div>
                  {vesselAlerts.length === 0 ? (
                    <p className="detail-panel__alerts-empty">No AIS silence alerts for this contact.</p>
                  ) : (
                    <ul className="detail-panel__alert-list">
                      {vesselAlerts.map((alert, index) => (
                        <li
                          key={`${alert.id ?? alert.t}-${index}`}
                          className={`detail-panel__alert ${alertSeverityClass(alert.severity)}`}
                        >
                          <div className="detail-panel__alert-title">{alert.title}</div>
                          <div className="detail-panel__alert-meta">{formatUtcShort(alert.t)}</div>
                          {alert.reason ? (
                            <div className="detail-panel__alert-reason">{alert.reason}</div>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </>
            );
          })()}
        </>
      )}
    </CollapsiblePanel>
  );
}
