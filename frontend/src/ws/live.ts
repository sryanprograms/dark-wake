export type AisEvent = {
  type: "ais";
  mmsi: number;
  t: string;
  lat: number;
  lon: number;
  sog?: number | null;
  cog?: number | null;
  heading?: number | null;
  name?: string | null;
  ship_type?: string | null;
  flag?: string | null;
  country?: string | null;
};

export type AisBatchEvent = {
  type: "ais_batch";
  vessels: Omit<AisEvent, "type">[];
};

export type LiveStateEvent = {
  type: "live_state";
  mode: "live";
  id: string;
  name: string;
  bbox: {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
  };
  vessel_count: number;
  ais_connected: boolean;
  current: string;
};

export type TracksBatchEvent = {
  type: "tracks_batch";
  tracks: VesselTrack[];
};

export type VesselTrack = {
  mmsi: number;
  path: [number, number][];
};

export type SarDetection = {
  id: string;
  t: string;
  lat: number;
  lon: number;
  length_m?: number | null;
  confidence?: number | null;
  scene_id?: string | null;
};

export type SarBatchEvent = {
  type: "sar_batch";
  detections: SarDetection[];
};

export type AlertEvent = {
  type: "alert";
  id?: number | null;
  kind: string;
  tier?: string;
  severity: string;
  mmsi?: number | null;
  t: string;
  title: string;
  reason?: string | null;
  details?: Record<string, unknown>;
  lat?: number | null;
  lon?: number | null;
};

export type LiveMessage =
  | AisEvent
  | AisBatchEvent
  | LiveStateEvent
  | TracksBatchEvent
  | SarBatchEvent
  | AlertEvent
  | { type: "ping" }
  | { type: "pong" };

export type LiveClient = {
  send: (msg: Record<string, unknown>) => void;
  close: () => void;
  ready: boolean;
};

export function connectLive(
  url: string,
  onMessage: (msg: LiveMessage) => void,
  onReady?: () => void,
): LiveClient {
  const ws = new WebSocket(url);
  const pending: Record<string, unknown>[] = [];
  let open = false;

  const flush = () => {
    while (pending.length > 0 && ws.readyState === WebSocket.OPEN) {
      const msg = pending.shift();
      if (msg) ws.send(JSON.stringify(msg));
    }
  };

  ws.onopen = () => {
    open = true;
    flush();
    onReady?.();
  };

  ws.onmessage = (event) => {
    onMessage(JSON.parse(event.data) as LiveMessage);
  };

  return {
    get ready() {
      return open && ws.readyState === WebSocket.OPEN;
    },
    send: (msg) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(msg));
      } else {
        pending.push(msg);
      }
    },
    close: () => ws.close(),
  };
}
