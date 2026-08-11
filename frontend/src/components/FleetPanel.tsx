import { useMemo, useRef, useState } from "react";
import * as ScrollArea from "@radix-ui/react-scroll-area";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Search, Ship } from "lucide-react";
import type { VesselPoint } from "../map/MapView";
import { formatLastReportLong, formatReportAge, formatUtcShort } from "../utils/time";
import { isVesselMoving } from "../utils/vesselFilters";
import { CollapsiblePanel } from "./CollapsiblePanel";
import { NationFilter } from "./NationFilter";
import { ShipTypeFilter } from "./ShipTypeFilter";

type FleetPanelProps = {
  vessels: VesselPoint[];
  allVessels: VesselPoint[];
  selectedMmsi: number | null;
  onSelect: (mmsi: number) => void;
  onCollapsedChange?: (collapsed: boolean) => void;
  shipTypeFilter: Set<string>;
  onShipTypeFilterChange: (types: Set<string>) => void;
  nationFilter: Set<string>;
  onNationFilterChange: (nations: Set<string>) => void;
  searchQuery: string;
  onSearchQueryChange: (query: string) => void;
  movingOnly: boolean;
  onMovingOnlyChange: (movingOnly: boolean) => void;
  onClearFilters: () => void;
  referenceTime?: string;
};

type FleetRow = VesselPoint & { moving: boolean };

const columnHelper = createColumnHelper<FleetRow>();

const columns = [
  columnHelper.accessor("mmsi", {
    header: "MMSI",
    cell: (info) => (
      <span className="fleet-cell fleet-cell--mono" title={String(info.getValue())}>
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor("name", {
    header: "Name",
    cell: (info) => {
      const name = info.getValue()?.trim();
      return (
        <span className="fleet-cell fleet-cell--name" title={name || undefined}>
          {name || "—"}
        </span>
      );
    },
  }),
  columnHelper.accessor("flag", {
    header: "Nation",
    cell: (info) => {
      const flag = info.getValue();
      const country = info.row.original.country;
      return (
        <span className="fleet-cell fleet-cell--mono" title={flag || undefined}>
          {country || flag || "—"}
        </span>
      );
    },
  }),
  columnHelper.accessor("ship_type", {
    header: "Type",
    cell: (info) => (
      <span className="fleet-cell fleet-cell--type" title={info.getValue() || undefined}>
        {info.getValue() || "—"}
      </span>
    ),
  }),
  columnHelper.accessor("sog", {
    header: "Speed",
    cell: (info) => {
      const sog = info.getValue();
      return (
        <span className={`fleet-cell fleet-cell--mono ${info.row.original.moving ? "" : "fleet-cell--idle"}`}>
          {sog != null ? `${sog.toFixed(1)}` : "—"}
        </span>
      );
    },
  }),
  columnHelper.accessor("heading", {
    header: "Heading",
    cell: (info) => (
      <span className="fleet-cell fleet-cell--mono">
        {info.getValue() != null && info.getValue() !== 511 ? `${info.getValue()}°` : "—"}
      </span>
    ),
  }),
  columnHelper.accessor("t", {
    header: "Last report",
    cell: (info) => (
      <span className="fleet-cell fleet-cell--mono fleet-cell--muted">
        {info.getValue() ? formatUtcShort(info.getValue()!) : "—"}
      </span>
    ),
  }),
];

export function FleetPanel({
  vessels,
  allVessels,
  selectedMmsi,
  onSelect,
  onCollapsedChange,
  shipTypeFilter,
  onShipTypeFilterChange,
  nationFilter,
  onNationFilterChange,
  searchQuery,
  onSearchQueryChange,
  movingOnly,
  onMovingOnlyChange,
  onClearFilters,
  referenceTime,
}: FleetPanelProps) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "mmsi", desc: false }]);
  const parentRef = useRef<HTMLDivElement>(null);

  const data = useMemo<FleetRow[]>(
    () =>
      vessels.map((v) => ({
        ...v,
        moving: isVesselMoving(v),
      })),
    [vessels],
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const rows = table.getRowModel().rows;

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 42,
    overscan: 12,
  });

  const filtersActive =
    shipTypeFilter.size > 0 ||
    nationFilter.size > 0 ||
    searchQuery.trim().length > 0 ||
    movingOnly;

  return (
    <CollapsiblePanel
      className="fleet-panel"
      title="Vessels"
      icon={<Ship size={14} />}
      count={rows.length}
      edge="left"
      onCollapsedChange={onCollapsedChange}
    >
      <div className="fleet-panel__filters">
        <div className="fleet-search">
          <Search size={14} />
          <input
            type="search"
            placeholder="Search name, nation, type, or ID…"
            value={searchQuery}
            onChange={(e) => onSearchQueryChange(e.target.value)}
          />
        </div>
        <ShipTypeFilter
          vessels={allVessels}
          selectedTypes={shipTypeFilter}
          onChange={onShipTypeFilterChange}
        />
        <NationFilter
          vessels={allVessels}
          selectedNations={nationFilter}
          onChange={onNationFilterChange}
        />
        <label className="fleet-toggle">
          <input
            type="checkbox"
            checked={movingOnly}
            onChange={(e) => onMovingOnlyChange(e.target.checked)}
          />
          Underway only
        </label>
      </div>

      {filtersActive ? (
        <div className="fleet-panel__filter-chip">
          <span>
            Showing {rows.length} of {allVessels.length} vessels on the map
          </span>
          <button type="button" className="fleet-panel__filter-clear" onClick={onClearFilters}>
            Clear filters
          </button>
        </div>
      ) : null}

      <ScrollArea.Root className="fleet-scroll">
        <ScrollArea.Viewport ref={parentRef} className="fleet-scroll__viewport">
          <div className="fleet-table-head">
            {table.getHeaderGroups().map((hg) =>
              hg.headers.map((header) => (
                <button
                  key={header.id}
                  type="button"
                  className="fleet-table-head__cell"
                  onClick={header.column.getToggleSortingHandler()}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {header.column.getIsSorted() === "asc" && " ↑"}
                  {header.column.getIsSorted() === "desc" && " ↓"}
                </button>
              )),
            )}
          </div>
          <div
            className="fleet-scroll__inner"
            style={{ height: `${virtualizer.getTotalSize()}px` }}
          >
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const row = rows[virtualRow.index];
              const selected = row.original.mmsi === selectedMmsi;
              const name = row.original.name?.trim();
              return (
                <button
                  key={row.original.mmsi}
                  type="button"
                  className={`fleet-row ${selected ? "fleet-row--selected" : ""} ${row.original.moving ? "" : "fleet-row--idle"}`}
                  style={{
                    transform: `translateY(${virtualRow.start}px)`,
                    height: `${virtualRow.size}px`,
                  }}
                  onClick={() => onSelect(row.original.mmsi)}
                >
                  <span className="fleet-row__mmsi">{row.original.mmsi}</span>
                  <span className="fleet-row__name" title={name || undefined}>
                    {name || "—"}
                  </span>
                  <span className="fleet-row__flag" title={row.original.flag || undefined}>
                    {row.original.country || row.original.flag || "—"}
                  </span>
                  <span className="fleet-row__type" title={row.original.ship_type || undefined}>
                    {row.original.ship_type || "—"}
                  </span>
                  <span className="fleet-row__sog">
                    {row.original.sog != null ? row.original.sog.toFixed(1) : "—"}
                  </span>
                  <span className="fleet-row__hdg">
                    {row.original.heading != null && row.original.heading !== 511
                      ? `${row.original.heading}°`
                      : "—"}
                  </span>
                  <span
                    className="fleet-row__time"
                    title={row.original.t ? formatLastReportLong(row.original.t, referenceTime) : undefined}
                  >
                    {row.original.t ? (
                      <>
                        <span className="fleet-row__time-clock">
                          {formatUtcShort(row.original.t)}
                        </span>
                        <span className="fleet-row__time-ago">
                          {formatReportAge(row.original.t, referenceTime)}
                        </span>
                      </>
                    ) : (
                      "—"
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </ScrollArea.Viewport>
        <ScrollArea.Scrollbar orientation="vertical" className="fleet-scroll__bar">
          <ScrollArea.Thumb className="fleet-scroll__thumb" />
        </ScrollArea.Scrollbar>
      </ScrollArea.Root>
    </CollapsiblePanel>
  );
}
