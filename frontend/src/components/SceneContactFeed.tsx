import { Radar } from "lucide-react";
import { formatUtcShort } from "../utils/time";
import type { SceneContact } from "../ws/timeline";

type SceneContactFeedProps = {
  contacts: SceneContact[];
  sceneTime?: string;
  onSelectMmsi?: (mmsi: number) => void;
};

function kindLabel(kind: SceneContact["kind"]): string {
  if (kind === "matched") return "Matched";
  if (kind === "dark") return "Dark";
  return "Ambiguous";
}

function kindClass(kind: SceneContact["kind"]): string {
  if (kind === "dark") return "scene-contact-feed__item--dark";
  if (kind === "matched") return "scene-contact-feed__item--matched";
  return "scene-contact-feed__item--ambiguous";
}

export function SceneContactFeed({ contacts, sceneTime, onSelectMmsi }: SceneContactFeedProps) {
  const darkCount = contacts.filter((c) => c.kind === "dark").length;

  return (
    <div className="event-feed scene-contact-feed">
      <div className="event-feed__header">
        <Radar size={14} />
        <span>SAR fusion</span>
        <span className="event-feed__count">{contacts.length}</span>
      </div>
      {sceneTime ? (
        <div className="scene-contact-feed__scene-time">{formatUtcShort(sceneTime)}</div>
      ) : null}
      <div className="event-feed__list">
        {contacts.length === 0 ? (
          <div className="event-feed__empty">No fusion contacts in this scene</div>
        ) : (
          contacts.map((contact) => (
            <button
              key={contact.id}
              type="button"
              className={`event-feed__item scene-contact-feed__item ${kindClass(contact.kind)}`}
              onClick={() => {
                if (contact.mmsi != null) onSelectMmsi?.(contact.mmsi);
              }}
            >
              <div className="event-feed__title">
                {kindLabel(contact.kind)}
                {contact.mmsi != null ? ` · MMSI ${contact.mmsi}` : ""}
              </div>
              <div className="event-feed__meta">
                {contact.confidence != null ? (
                  <span>{Math.round(contact.confidence * 100)}% conf</span>
                ) : null}
                {contact.distance_m != null ? <span>{Math.round(contact.distance_m)} m</span> : null}
              </div>
            </button>
          ))
        )}
      </div>
      {darkCount > 0 ? (
        <div className="scene-contact-feed__dark-hint">{darkCount} dark contact{darkCount === 1 ? "" : "s"}</div>
      ) : null}
    </div>
  );
}
