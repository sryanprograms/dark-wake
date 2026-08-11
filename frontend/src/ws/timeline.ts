export type PlayheadMode = "live" | "historical" | "scene";

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
  source?: "db_snapshot";
};

export type VesselTrack = {
  mmsi: number;
  path: [number, number][];
};

export type TracksBatchEvent = {
  type: "tracks_batch";
  tracks: VesselTrack[];
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

export type SceneContact = {
  id: string;
  kind: "matched" | "dark" | "ambiguous";
  sar_lat: number;
  sar_lon: number;
  ais_lat?: number | null;
  ais_lon?: number | null;
  mmsi?: number | null;
  confidence?: number | null;
  distance_m?: number | null;
};

export type TimelineScene = {
  id: string;
  t: string;
  scene_id?: string;
  detection_count?: number;
  dark_count?: number;
};

export type TimelineStateEvent = {
  type: "timeline_state";
  mode: PlayheadMode;
  current?: string;
  playhead?: string;
  data_start: string;
  data_end: string;
  live_edge: string;
  playing?: boolean;
  speed?: number;
  current_scene_id?: string | null;
  scenes?: TimelineScene[];
  id?: string;
  name?: string;
  bbox?: {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
  };
  vessel_count?: number;
  position_count?: number;
  ais_connected?: boolean;
};

export type StateEvent = {
  type: "state";
  current: string;
  playing: boolean;
  mode?: PlayheadMode;
  current_scene_id?: string | null;
};

export type SceneFrameEvent = {
  type: "scene_frame";
  scene_id: string;
  t: string;
  sar: SarDetection[];
  contacts: SceneContact[];
  ais?: Omit<AisEvent, "type">[];
  tracks?: VesselTrack[];
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

export type TimelineMessage =
  | AisEvent
  | AisBatchEvent
  | TracksBatchEvent
  | TimelineStateEvent
  | StateEvent
  | SceneFrameEvent
  | AlertEvent
  | { type: "ping" }
  | { type: "pong" };

export type TimelineClient = {
  seek: (t: string) => void;
  snapScene: (sceneId: string) => void;
  goLive: () => void;
  play: () => void;
  pause: () => void;
  speed: (multiplier: number) => void;
  send: (msg: Record<string, unknown>) => void;
  close: () => void;
  ready: boolean;
};

export function connectTimeline(
  url: string,
  onMessage: (msg: TimelineMessage) => void,
  onReady?: () => void,
): TimelineClient {
  const ws = new WebSocket(url);
  const pending: Record<string, unknown>[] = [];
  let open = false;

  const flush = () => {
    while (pending.length > 0 && ws.readyState === WebSocket.OPEN) {
      const msg = pending.shift();
      if (msg) ws.send(JSON.stringify(msg));
    }
  };

  const sendRaw = (msg: Record<string, unknown>) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    } else {
      pending.push(msg);
    }
  };

  ws.onopen = () => {
    open = true;
    flush();
    onReady?.();
  };

  ws.onmessage = (event) => {
    onMessage(JSON.parse(event.data) as TimelineMessage);
  };

  return {
    get ready() {
      return open && ws.readyState === WebSocket.OPEN;
    },
    send: sendRaw,
    seek: (t) => sendRaw({ action: "seek", t }),
    snapScene: (sceneId) => sendRaw({ action: "snap_scene", scene_id: sceneId }),
    goLive: () => sendRaw({ action: "go_live" }),
    play: () => sendRaw({ action: "play" }),
    pause: () => sendRaw({ action: "pause" }),
    speed: (multiplier) => sendRaw({ action: "speed", multiplier }),
    close: () => ws.close(),
  };
}
