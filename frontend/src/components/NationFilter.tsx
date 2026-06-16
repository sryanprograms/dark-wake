import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Globe } from "lucide-react";
import type { VesselPoint } from "../map/MapView";
import { nationCounts } from "../utils/nations";

type NationFilterProps = {
  vessels: VesselPoint[];
  selectedNations: Set<string>;
  onChange: (selectedNations: Set<string>) => void;
};

function filterSummary(selected: Set<string>): string {
  if (selected.size === 0) return "All nations";
  const nations = [...selected].sort((a, b) => a.localeCompare(b));
  if (nations.length === 1) return nations[0];
  if (nations.length === 2) return `${nations[0]}, ${nations[1]}`;
  return `${nations[0]}, ${nations[1]} +${nations.length - 2}`;
}

export function NationFilter({ vessels, selectedNations, onChange }: NationFilterProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const options = useMemo(() => nationCounts(vessels), [vessels]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  const allNations = useMemo(() => options.map((option) => option.nation), [options]);

  const toggleNation = (nation: string) => {
    const next = new Set(selectedNations);
    if (next.has(nation)) next.delete(nation);
    else next.add(nation);
    onChange(next);
  };

  const selectAll = () => onChange(new Set(allNations));
  const deselectAll = () => onChange(new Set());

  const active = selectedNations.size > 0;

  return (
    <div className={`ship-type-filter${open ? " ship-type-filter--open" : ""}`} ref={rootRef}>
      <button
        type="button"
        className={`ship-type-filter__trigger${active ? " ship-type-filter__trigger--active" : ""}`}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <Globe size={14} />
        <span className="ship-type-filter__label">{filterSummary(selectedNations)}</span>
        <ChevronDown size={14} className="ship-type-filter__chevron" />
      </button>

      {open && (
        <div className="ship-type-filter__menu" role="listbox" aria-multiselectable="true">
          <div className="ship-type-filter__menu-head">
            <span>Nations</span>
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
            <div className="ship-type-filter__empty">No nations in view</div>
          ) : (
            options.map(({ nation, flag, count }) => (
              <label key={nation} className="ship-type-filter__option">
                <input
                  type="checkbox"
                  checked={selectedNations.has(nation)}
                  onChange={() => toggleNation(nation)}
                />
                <span className="ship-type-filter__option-label">
                  {flag ? `${nation} (${flag})` : nation}
                </span>
                <span className="ship-type-filter__option-count">{count}</span>
              </label>
            ))
          )}
        </div>
      )}
    </div>
  );
}
