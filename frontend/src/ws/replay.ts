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

export type WindowPreset = "24h" | "3d" | "7d";

export type ScenarioEvent = {
  type: "scenario";
  id: string;
  name: string;
  bbox: {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
  };
  start: string;
  end: string;
  data_start: string;
  data_end: string;
  window_preset: WindowPreset;
  current?: string;
  position_count?: number;
  loaded?: boolean;
};

export type StateEvent = {
  type: "state";
  current: string;
  playing: boolean;
};

export type TracksBatchEvent = {
  type: "tracks_batch";
  tracks: VesselTrack[];
};

export type VesselTrack = {
  mmsi: number;
  path: [number, number][];
};

export type ReplayMessage = AisEvent | AisBatchEvent | TracksBatchEvent | ScenarioEvent | StateEvent;

export type ReplayClient = {
  send: (msg: Record<string, unknown>) => void;
  close: () => void;
  ready: boolean;
};

export function connectReplay(
  url: string,
  onMessage: (msg: ReplayMessage) => void,
  onReady?: () => void,
): ReplayClient {
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
    onMessage(JSON.parse(event.data) as ReplayMessage);
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
