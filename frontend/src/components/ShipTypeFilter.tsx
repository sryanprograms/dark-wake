import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Filter } from "lucide-react";
import type { VesselPoint } from "../map/MapView";
import { shipTypeCounts } from "../utils/shipTypes";

type ShipTypeFilterProps = {
  vessels: VesselPoint[];
  selectedTypes: Set<string>;
  onChange: (selectedTypes: Set<string>) => void;
};

function filterSummary(selected: Set<string>): string {
  if (selected.size === 0) return "All ship types";
  const types = [...selected].sort((a, b) => a.localeCompare(b));
  if (types.length === 1) return types[0];
  if (types.length === 2) return `${types[0]}, ${types[1]}`;
  return `${types[0]}, ${types[1]} +${types.length - 2}`;
}

export function ShipTypeFilter({ vessels, selectedTypes, onChange }: ShipTypeFilterProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const options = useMemo(() => shipTypeCounts(vessels), [vessels]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  const allTypes = useMemo(() => options.map((option) => option.type), [options]);

  const toggleType = (type: string) => {
    const next = new Set(selectedTypes);
    if (next.has(type)) next.delete(type);
    else next.add(type);
    onChange(next);
  };

  const selectAll = () => onChange(new Set(allTypes));
  const deselectAll = () => onChange(new Set());

  const active = selectedTypes.size > 0;

  return (
    <div className={`ship-type-filter${open ? " ship-type-filter--open" : ""}`} ref={rootRef}>
      <button
        type="button"
        className={`ship-type-filter__trigger${active ? " ship-type-filter__trigger--active" : ""}`}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <Filter size={14} />
        <span className="ship-type-filter__label">{filterSummary(selectedTypes)}</span>
        <ChevronDown size={14} className="ship-type-filter__chevron" />
      </button>

      {open && (
        <div className="ship-type-filter__menu" role="listbox" aria-multiselectable="true">
          <div className="ship-type-filter__menu-head">
            <span>Ship types</span>
            {options.length > 0 && (
              <div className="ship-type-filter__menu-actions">
                <button type="button" className="ship-type-filter__action" onClick={selectAll}>
                  All
                </button>
                <button type="button" className="ship-type-filter__action" onClick={deselectAll}>
                  None
                </button>
              </div>
            )}
          </div>
          {options.length === 0 ? (
            <div className="ship-type-filter__empty">No ship types in view</div>
          ) : (
            options.map(({ type, count }) => (
              <label key={type} className="ship-type-filter__option">
                <input
                  type="checkbox"
                  checked={selectedTypes.has(type)}
                  onChange={() => toggleType(type)}
                />
                <span className="ship-type-filter__option-label">{type}</span>
                <span className="ship-type-filter__option-count">{count}</span>
              </label>
            ))
          )}
        </div>
      )}
    </div>
  );
}
