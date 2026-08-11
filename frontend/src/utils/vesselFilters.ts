import type { VesselPoint } from "../map/MapView";
import { filterVesselsByNation } from "./nations";
import { filterVesselsByShipType } from "./shipTypes";

export function isVesselMoving(vessel: VesselPoint): boolean {
  return vessel.sog != null && vessel.sog > 0.5;
}

export function matchesVesselSearch(vessel: VesselPoint, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    String(vessel.mmsi).includes(q) ||
    (vessel.name?.toLowerCase().includes(q) ?? false) ||
    (vessel.flag?.toLowerCase().includes(q) ?? false) ||
    (vessel.country?.toLowerCase().includes(q) ?? false) ||
    (vessel.ship_type?.toLowerCase().includes(q) ?? false)
  );
}

export type VesselFilterOptions = {
  shipTypeFilter: Set<string>;
  nationFilter: Set<string>;
  searchQuery?: string;
  movingOnly?: boolean;
};

export function filterVessels(
  vessels: VesselPoint[],
  { shipTypeFilter, nationFilter, searchQuery = "", movingOnly = false }: VesselFilterOptions,
): VesselPoint[] {
  let list = filterVesselsByShipType(vessels, shipTypeFilter);
  list = filterVesselsByNation(list, nationFilter);
  if (searchQuery.trim()) {
    list = list.filter((vessel) => matchesVesselSearch(vessel, searchQuery));
  }
  if (movingOnly) {
    list = list.filter(isVesselMoving);
  }
  return list;
}
