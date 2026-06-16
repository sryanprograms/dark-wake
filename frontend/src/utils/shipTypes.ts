import type { VesselPoint } from "../map/MapView";

export const UNKNOWN_SHIP_TYPE = "Unknown";

export function shipTypeLabel(type: string | null | undefined): string {
  return type?.trim() || UNKNOWN_SHIP_TYPE;
}

export function shipTypeCounts(vessels: VesselPoint[]): { type: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const vessel of vessels) {
    const label = shipTypeLabel(vessel.ship_type);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count || a.type.localeCompare(b.type));
}

export function matchesShipTypeFilter(
  vessel: VesselPoint,
  selectedTypes: Set<string>,
): boolean {
  if (selectedTypes.size === 0) return true;
  return selectedTypes.has(shipTypeLabel(vessel.ship_type));
}

export function filterVesselsByShipType(
  vessels: VesselPoint[],
  selectedTypes: Set<string>,
): VesselPoint[] {
  if (selectedTypes.size === 0) return vessels;
  return vessels.filter((vessel) => matchesShipTypeFilter(vessel, selectedTypes));
}
