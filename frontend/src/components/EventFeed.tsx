import { AlertTriangle } from "lucide-react";
import { formatUtcShort } from "../utils/time";
import { alertKindLabel, alertTierLabel } from "../utils/alerts";
import type { AlertEvent } from "../ws/timeline";

type EventFeedProps = {
  events: AlertEvent[];
  onSelectMmsi?: (mmsi: number) => void;
};

function severityClass(severity: string): string {
  if (severity === "high") return "event-feed__item--high";
  if (severity === "medium") return "event-feed__item--medium";
  return "event-feed__item--low";
}

export function EventFeed({ events, onSelectMmsi }: EventFeedProps) {
  return (
    <div className="event-feed">
      <div className="event-feed__header">
        <AlertTriangle size={14} />
        <span>Needs attention</span>
        <span className="event-feed__count">{events.length}</span>
      </div>
      <div className="event-feed__list">
        {events.length === 0 ? (
          <div className="event-feed__empty">All clear — no unusual activity detected</div>
        ) : (
          events.map((event, index) => (
            <button
              key={`${event.id ?? event.t}-${index}`}
              type="button"
              className={`event-feed__item ${severityClass(event.severity)}`}
              onClick={() => {
                if (event.mmsi != null) onSelectMmsi?.(event.mmsi);
              }}
            >
              <div className="event-feed__title">{event.title}</div>
              <div className="event-feed__meta">
                <span>{formatUtcShort(event.t)}</span>
                <span>{alertKindLabel(event.kind)}</span>
                {alertTierLabel(event.tier) ? <span>{alertTierLabel(event.tier)}</span> : null}
              </div>
              {event.reason ? <div className="event-feed__reason">{event.reason}</div> : null}
            </button>
          ))
        )}
      </div>
    </div>
  );
}
