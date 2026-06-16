import type { VesselPoint } from "../map/MapView";

export const UNKNOWN_NATION = "Unknown";

export function nationLabel(vessel: VesselPoint): string {
  return vessel.country?.trim() || vessel.flag?.trim() || UNKNOWN_NATION;
}

export function nationFlag(vessel: VesselPoint): string | undefined {
  const flag = vessel.flag?.trim();
  return flag || undefined;
}

export function nationCounts(
  vessels: VesselPoint[],
): { nation: string; flag?: string; count: number }[] {
  const counts = new Map<string, { flag?: string; count: number }>();
  for (const vessel of vessels) {
    const label = nationLabel(vessel);
    const existing = counts.get(label);
    const flag = nationFlag(vessel);
    if (existing) {
      existing.count += 1;
      if (!existing.flag && flag) existing.flag = flag;
    } else {
      counts.set(label, { flag, count: 1 });
    }
  }
  return [...counts.entries()]
    .map(([nation, { flag, count }]) => ({ nation, flag, count }))
    .sort((a, b) => b.count - a.count || a.nation.localeCompare(b.nation));
}

export function matchesNationFilter(vessel: VesselPoint, selectedNations: Set<string>): boolean {
  if (selectedNations.size === 0) return true;
  return selectedNations.has(nationLabel(vessel));
}

export function filterVesselsByNation(
  vessels: VesselPoint[],
  selectedNations: Set<string>,
): VesselPoint[] {
  if (selectedNations.size === 0) return vessels;
  return vessels.filter((vessel) => matchesNationFilter(vessel, selectedNations));
}
