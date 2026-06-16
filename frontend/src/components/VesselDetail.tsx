import { useEffect, useState } from "react";
import { AlertTriangle, Anchor, Crosshair } from "lucide-react";
import type { VesselPoint } from "../map/MapView";
import { formatUtc } from "../utils/time";
import { CollapsiblePanel } from "./CollapsiblePanel";

type VesselDetailProps = {
  vessel: VesselPoint | null;
  onCenter?: () => void;
  onCollapsedChange?: (collapsed: boolean) => void;
};

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-row">
      <span className="detail-row__label">{label}</span>
      <span className="detail-row__value">{value}</span>
    </div>
  );
}

export function VesselDetail({ vessel, onCenter, onCollapsedChange }: VesselDetailProps) {
  const [collapsed, setCollapsed] = useState(!vessel);

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
                  </div>
                  <p className="detail-panel__alerts-empty">
                    No anomalies detected. Dark-ship fusion arrives in Phase 2.
                  </p>
                </div>
              </>
            );
          })()}
        </>
      )}
    </CollapsiblePanel>
  );
}
