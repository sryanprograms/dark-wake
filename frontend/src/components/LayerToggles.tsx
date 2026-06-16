import { Cable, Layers, MapPin, Radar, Route, Ship } from "lucide-react";
import type { LayerVisibility } from "../types/layers";

type LayerTogglesProps = {
  layers: LayerVisibility;
  onChange: (layers: LayerVisibility) => void;
};

const ITEMS: { key: keyof LayerVisibility; label: string; icon: typeof Ship }[] = [
  { key: "vessels", label: "Contacts", icon: Ship },
  { key: "tracks", label: "Tracks", icon: Route },
  { key: "sar", label: "SAR", icon: Radar },
  { key: "cables", label: "Cables", icon: Cable },
  { key: "corridor", label: "Corridor", icon: MapPin },
];

export function LayerToggles({ layers, onChange }: LayerTogglesProps) {
  return (
    <div className="layer-toggles">
      <div className="layer-toggles__title">
        <Layers size={14} />
        Layers
      </div>
      {ITEMS.map(({ key, label, icon: Icon }) => (
        <label key={key} className="layer-toggle">
          <input
            type="checkbox"
            checked={layers[key]}
            onChange={(e) => onChange({ ...layers, [key]: e.target.checked })}
          />
          <Icon size={13} />
          {label}
        </label>
      ))}
    </div>
  );
}
