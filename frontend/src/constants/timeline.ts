/** AOI and timeline constants — keep in sync with backend `app/config/aoi.py`. */
export const DEFAULT_BBOX = {
  min_lat: 54.8,
  max_lat: 56.8,
  min_lon: 10.2,
  max_lon: 13.2,
} as const;

/** Seek/playhead snaps to live when within this many ms of the live edge. */
export const LIVE_EDGE_MS = 30_000;
