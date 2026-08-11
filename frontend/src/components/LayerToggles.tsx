import { Cable, Layers, MapPin, Radar, Route, Ship } from "lucide-react";
import type { LayerVisibility } from "../types/layers";
import type { PlayheadMode } from "../ws/timeline";

type LayerTogglesProps = {
  layers: LayerVisibility;
  playheadMode: PlayheadMode;
  onChange: (layers: LayerVisibility) => void;
};

const BASE_ITEMS: { key: keyof LayerVisibility; label: string; icon: typeof Ship }[] = [
  { key: "vessels", label: "Ships", icon: Ship },
  { key: "tracks", label: "Tracks", icon: Route },
  { key: "cables", label: "Cables", icon: Cable },
  { key: "corridor", label: "Monitored area", icon: MapPin },
];

const SCENE_ITEMS: { key: keyof LayerVisibility; label: string; icon: typeof Ship }[] = [
  { key: "sar", label: "Radar", icon: Radar },
];

export function LayerToggles({ layers, playheadMode, onChange }: LayerTogglesProps) {
  const inSceneMode = playheadMode === "scene";
  const items = inSceneMode ? [...BASE_ITEMS.slice(0, 2), ...SCENE_ITEMS, ...BASE_ITEMS.slice(2)] : BASE_ITEMS;

  return (
    <div className="layer-toggles">
      <div className="layer-toggles__title">
        <Layers size={14} />
        Layers
      </div>
      {!inSceneMode ? (
        <p className="layer-toggles__hint">Radar layers appear in SAR Scene mode</p>
      ) : null}
      {items.map(({ key, label, icon: Icon }) => (
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
