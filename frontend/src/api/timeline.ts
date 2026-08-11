import type { TimelineScene } from "../ws/timeline";

export type TimelineBounds = {
  data_start: string;
  data_end: string;
  live_edge: string;
  ais_count?: number;
  scene_count?: number;
};

export async function fetchTimelineBounds(): Promise<TimelineBounds | null> {
  try {
    const response = await fetch("/timeline/bounds");
    if (!response.ok) return null;
    return (await response.json()) as TimelineBounds;
  } catch {
    return null;
  }
}

export async function fetchTimelineScenes(): Promise<TimelineScene[]> {
  try {
    const response = await fetch("/timeline/scenes");
    if (!response.ok) return [];
    return (await response.json()) as TimelineScene[];
  } catch {
    return [];
  }
}
