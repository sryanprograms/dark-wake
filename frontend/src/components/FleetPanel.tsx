import { useMemo, useRef, useState } from "react";
import * as ScrollArea from "@radix-ui/react-scroll-area";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Search, Ship } from "lucide-react";
import type { VesselPoint } from "../map/MapView";
import { formatUtcShort } from "../utils/time";
import { matchesShipTypeFilter } from "../utils/shipTypes";
import { CollapsiblePanel } from "./CollapsiblePanel";
import { ShipTypeFilter } from "./ShipTypeFilter";

type FleetPanelProps = {
  vessels: VesselPoint[];
  selectedMmsi: number | null;
  onSelect: (mmsi: number) => void;
  onCollapsedChange?: (collapsed: boolean) => void;
  shipTypeFilter: Set<string>;
  onShipTypeFilterChange: (types: Set<string>) => void;
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
    header: "Flag",
    cell: (info) => {
      const flag = info.getValue();
      const country = info.row.original.country;
      return (
        <span className="fleet-cell fleet-cell--mono" title={country || undefined}>
          {flag || "—"}
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
    header: "SOG",
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
    header: "HDG",
    cell: (info) => (
      <span className="fleet-cell fleet-cell--mono">
        {info.getValue() != null && info.getValue() !== 511 ? `${info.getValue()}°` : "—"}
      </span>
    ),
  }),
  columnHelper.accessor("t", {
    header: "Last",
    cell: (info) => (
      <span className="fleet-cell fleet-cell--mono fleet-cell--muted">
        {info.getValue() ? formatUtcShort(info.getValue()!) : "—"}
      </span>
    ),
  }),
];

export function FleetPanel({
  vessels,
  selectedMmsi,
  onSelect,
  onCollapsedChange,
  shipTypeFilter,
  onShipTypeFilterChange,
}: FleetPanelProps) {
  const [query, setQuery] = useState("");
  const [movingOnly, setMovingOnly] = useState(false);
  const [sorting, setSorting] = useState<SortingState>([{ id: "mmsi", desc: false }]);
  const parentRef = useRef<HTMLDivElement>(null);

  const data = useMemo<FleetRow[]>(
    () =>
      vessels.map((v) => ({
        ...v,
        moving: v.sog != null && v.sog > 0.5,
      })),
    [vessels],
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter: query },
    onSortingChange: setSorting,
    globalFilterFn: (row, _columnId, filterValue) => {
      const q = String(filterValue).toLowerCase();
      if (!q) return true;
      const v = row.original;
      return (
        String(v.mmsi).includes(q) ||
        (v.name?.toLowerCase().includes(q) ?? false) ||
        (v.flag?.toLowerCase().includes(q) ?? false) ||
        (v.country?.toLowerCase().includes(q) ?? false) ||
        (v.ship_type?.toLowerCase().includes(q) ?? false)
      );
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const filteredRows = useMemo(() => {
    let rows = table.getRowModel().rows;
    if (movingOnly) rows = rows.filter((r) => r.original.moving);
    if (shipTypeFilter.size > 0) {
      rows = rows.filter((r) => matchesShipTypeFilter(r.original, shipTypeFilter));
    }
    return rows;
  }, [table, movingOnly, shipTypeFilter, query, sorting, data]);

  const virtualizer = useVirtualizer({
    count: filteredRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 12,
  });

  return (
    <CollapsiblePanel
      className="fleet-panel"
      title="Order of battle"
      icon={<Ship size={14} />}
      count={filteredRows.length}
      edge="left"
      onCollapsedChange={onCollapsedChange}
    >
      <div className="fleet-panel__filters">
        <div className="fleet-search">
          <Search size={14} />
          <input
            type="search"
            placeholder="Search MMSI, name, flag, type…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <ShipTypeFilter
          vessels={vessels}
          selectedTypes={shipTypeFilter}
          onChange={onShipTypeFilterChange}
        />
        <label className="fleet-toggle">
          <input
            type="checkbox"
            checked={movingOnly}
            onChange={(e) => setMovingOnly(e.target.checked)}
          />
          Moving only
        </label>
      </div>

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

      <ScrollArea.Root className="fleet-scroll">
        <ScrollArea.Viewport ref={parentRef} className="fleet-scroll__viewport">
          <div
            className="fleet-scroll__inner"
            style={{ height: `${virtualizer.getTotalSize()}px` }}
          >
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const row = filteredRows[virtualRow.index];
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
                  <span className="fleet-row__flag" title={row.original.country || undefined}>
                    {row.original.flag || "—"}
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
                  <span className="fleet-row__time">
                    {row.original.t ? formatUtcShort(row.original.t) : "—"}
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
