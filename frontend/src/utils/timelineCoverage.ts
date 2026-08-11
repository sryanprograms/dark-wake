import { toMs } from "./time";

const MS_PER_HOUR = 3_600_000;
const THIN_HISTORY_HOURS = 2;
const THIN_POSITION_THRESHOLD = 100;

export function formatTimelineSpan(dataStart: string, liveEdge: string): string {
  const hours = Math.max(1, Math.round((toMs(liveEdge) - toMs(dataStart)) / MS_PER_HOUR));
  if (hours < 48) return `${hours}h`;
  const days = Math.round(hours / 24);
  return `${days}d`;
}

export function formatStoredCount(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
  return count.toLocaleString();
}

/** True when persisted AIS history is too thin to trust empty-map states. */
export function isHistoryThin(
  positionCount: number | null,
  dataStart: string,
  liveEdge: string,
): boolean {
  if (positionCount == null || positionCount === 0) return true;
  const spanMs = toMs(liveEdge) - toMs(dataStart);
  if (spanMs < THIN_HISTORY_HOURS * MS_PER_HOUR && positionCount < THIN_POSITION_THRESHOLD) {
    return true;
  }
  return positionCount < 10;
}

export type EmptyMapState =
  | { kind: "none" }
  | { kind: "live_disconnected" }
  | { kind: "live_empty_corridor" }
  | { kind: "historical_building" }
  | { kind: "historical_empty" }
  | { kind: "scene_no_ais" }
  | { kind: "scene_empty_corridor" };

export function resolveEmptyMapState(args: {
  connected: boolean;
  playheadMode: "live" | "historical" | "scene";
  vesselCount: number;
  aisConnected: boolean;
  positionCount: number | null;
  dataStart: string;
  liveEdge: string;
  sarDetectionCount: number;
}): EmptyMapState {
  const {
    connected,
    playheadMode,
    vesselCount,
    aisConnected,
    positionCount,
    dataStart,
    liveEdge,
    sarDetectionCount,
  } = args;

  if (!connected || vesselCount > 0) return { kind: "none" };

  if (playheadMode === "live") {
    if (!aisConnected) return { kind: "live_disconnected" };
    return { kind: "live_empty_corridor" };
  }

  if (playheadMode === "scene") {
    if (sarDetectionCount > 0 && isHistoryThin(positionCount, dataStart, liveEdge)) {
      return { kind: "scene_no_ais" };
    }
    if (isHistoryThin(positionCount, dataStart, liveEdge)) {
      return { kind: "historical_building" };
    }
    return { kind: "scene_empty_corridor" };
  }

  if (isHistoryThin(positionCount, dataStart, liveEdge)) {
    return { kind: "historical_building" };
  }
  return { kind: "historical_empty" };
}

export function emptyMapCopy(state: EmptyMapState): { title: string; body: string } | null {
  switch (state.kind) {
    case "none":
      return null;
    case "live_disconnected":
      return {
        title: "Live ship data isn't connected",
        body: "The monitoring area is ready, but vessel positions aren't streaming in. Contact your administrator to restore the feed.",
      };
    case "live_empty_corridor":
      return {
        title: "No vessels in the monitored area",
        body: "The live feed is active, but no ships are in the corridor right now.",
      };
    case "historical_building":
      return {
        title: "AIS history is still building",
        body: "Stored positions accumulate while monitoring runs. Scene comparison and historical scrubbing improve over time.",
      };
    case "historical_empty":
      return {
        title: "No vessels at this time",
        body: "Stored AIS data exists for this window, but no ships were in the monitored area at the playhead time.",
      };
    case "scene_no_ais":
      return {
        title: "No AIS data for this scene yet",
        body: "Radar detections are visible, but not enough AIS history was recorded at this pass time for fusion.",
      };
    case "scene_empty_corridor":
      return {
        title: "No vessels in the monitored area",
        body: "AIS history exists, but no ships were in the corridor at this scene time.",
      };
  }
}
