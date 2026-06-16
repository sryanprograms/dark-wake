import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchCables, type CableSegment } from "./api/cables";
import { EventFeed } from "./components/EventFeed";
import { FleetPanel } from "./components/FleetPanel";
import { LayerToggles } from "./components/LayerToggles";
import { TimelineDock } from "./components/TimelineDock";
import { TopBar } from "./components/TopBar";
import { VesselDetail } from "./components/VesselDetail";
import { MapView, VesselPoint, VesselTrack, type SarDetection } from "./map/MapView";
import { DEFAULT_LAYERS, LayerVisibility } from "./types/layers";
import { filterVesselsByShipType } from "./utils/shipTypes";
import { filterVesselsByNation } from "./utils/nations";
import { toMs } from "./utils/time";
import {
  AlertEvent,
  connectLive,
  LiveMessage,
  LiveStateEvent,
} from "./ws/live";
import { AisEvent, connectReplay, ReplayMessage, WindowPreset } from "./ws/replay";

type AppMode = "live" | "replay";

type Scenario = {
  id: string;
  name: string;
  start: string;
  end: string;
  dataStart: string;
  dataEnd: string;
  windowPreset: WindowPreset;
  bbox: {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
  };
};

const WINDOW_PRESETS: WindowPreset[] = ["24h", "3d", "7d"];

function getInitialMode(): AppMode {
  const params = new URLSearchParams(window.location.search);
  return params.get("mode") === "replay" ? "replay" : "live";
}

function wsBaseUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return (
    (import.meta.env.VITE_WS_URL as string | undefined) ??
    `${proto}://${window.location.host}`
  );
}

function aisToVessel(msg: AisEvent | Omit<AisEvent, "type">): VesselPoint {
  return {
    mmsi: msg.mmsi,
    lat: msg.lat,
    lon: msg.lon,
    heading: msg.heading,
    sog: msg.sog,
    cog: msg.cog,
    name: msg.name,
    ship_type: msg.ship_type,
    flag: msg.flag,
    country: msg.country,
    t: msg.t,
  };
}

function vesselsFromBatch(vessels: Omit<AisEvent, "type">[]): Map<number, VesselPoint> {
  return new Map(vessels.map((v) => [v.mmsi, aisToVessel(v)]));
}

function liveStateToScenario(msg: LiveStateEvent): Scenario {
  const now = msg.current;
  return {
    id: msg.id,
    name: msg.name,
    start: now,
    end: now,
    dataStart: now,
    dataEnd: now,
    windowPreset: "24h",
    bbox: msg.bbox,
  };
}

export default function App() {
  const [mode, setMode] = useState<AppMode>(getInitialMode);
  const clientRef = useRef<ReturnType<typeof connectReplay> | ReturnType<typeof connectLive> | null>(null);
  const [vessels, setVessels] = useState<Map<number, VesselPoint>>(new Map());
  const [tracks, setTracks] = useState<VesselTrack[]>([]);
  const [sarDetections, setSarDetections] = useState<SarDetection[]>([]);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [current, setCurrent] = useState("");
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const [windowPreset, setWindowPreset] = useState<WindowPreset>("24h");
  const [connected, setConnected] = useState(false);
  const [aisConnected, setAisConnected] = useState(false);
  const [positionCount, setPositionCount] = useState<number | null>(null);
  const [selectedMmsi, setSelectedMmsi] = useState<number | null>(null);
  const [centerRequest, setCenterRequest] = useState<{
    lat: number;
    lon: number;
    token: number;
  } | null>(null);
  const [layers, setLayers] = useState<LayerVisibility>(DEFAULT_LAYERS);
  const [cables, setCables] = useState<CableSegment[]>([]);
  const [fleetCollapsed, setFleetCollapsed] = useState(false);
  const [detailCollapsed, setDetailCollapsed] = useState(true);
  const [shipTypeFilter, setShipTypeFilter] = useState<Set<string>>(() => new Set());
  const [nationFilter, setNationFilter] = useState<Set<string>>(() => new Set());

  const applyAis = useCallback((msg: AisEvent | Omit<AisEvent, "type">) => {
    setVessels((prev) => {
      const next = new Map(prev);
      next.set(msg.mmsi, aisToVessel(msg));
      return next;
    });
  }, []);

  const switchMode = useCallback((next: AppMode) => {
    const url = new URL(window.location.href);
    if (next === "replay") {
      url.searchParams.set("mode", "replay");
    } else {
      url.searchParams.delete("mode");
    }
    window.history.replaceState({}, "", url);
    setMode(next);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchCables(scenario?.bbox)
      .then((segments) => {
        if (!cancelled) setCables(segments);
      })
      .catch(() => {
        if (!cancelled) setCables([]);
      });
    return () => {
      cancelled = true;
    };
  }, [scenario?.bbox]);

  useEffect(() => {
    clientRef.current?.close();
    setConnected(false);
    setVessels(new Map());
    setTracks([]);
    setSarDetections([]);
    setAlerts([]);
    setSelectedMmsi(null);
    setPlaying(false);

    if (mode === "live") {
      const client = connectLive(`${wsBaseUrl()}/ws/live`, (msg: LiveMessage) => {
        if (msg.type === "live_state") {
          setScenario(liveStateToScenario(msg));
          setCurrent(msg.current);
          setPositionCount(msg.vessel_count);
          setAisConnected(msg.ais_connected);
          setConnected(true);
        } else if (msg.type === "ais_batch") {
          setVessels(vesselsFromBatch(msg.vessels));
        } else if (msg.type === "tracks_batch") {
          setTracks(msg.tracks);
        } else if (msg.type === "ais") {
          applyAis(msg);
          setCurrent(msg.t);
        } else if (msg.type === "sar_batch") {
          setSarDetections((prev) => {
            const byId = new Map(prev.map((d) => [d.id, d]));
            for (const det of msg.detections) {
              byId.set(det.id, det);
            }
            return Array.from(byId.values());
          });
        } else if (msg.type === "alert") {
          setAlerts((prev) => [msg, ...prev].slice(0, 100));
        }
      });
      clientRef.current = client;
      return () => client.close();
    }

    const client = connectReplay(`${wsBaseUrl()}/ws/replay`, (msg: ReplayMessage) => {
      if (msg.type === "scenario") {
        setScenario({
          id: msg.id,
          name: msg.name,
          start: msg.start,
          end: msg.end,
          dataStart: msg.data_start,
          dataEnd: msg.data_end,
          windowPreset: msg.window_preset,
          bbox: msg.bbox,
        });
        setWindowPreset(msg.window_preset);
        setCurrent(msg.current ?? msg.end);
        setPositionCount(msg.position_count ?? null);
        setConnected(true);
        setPlaying(false);
        setVessels(new Map());
        setTracks([]);
        setSelectedMmsi(null);
        setShipTypeFilter(new Set());
        setNationFilter(new Set());
        clientRef.current?.send({ action: "speed", multiplier: speed });
      } else if (msg.type === "state") {
        setCurrent(msg.current);
        setPlaying(msg.playing);
      } else if (msg.type === "ais_batch") {
        setVessels(vesselsFromBatch(msg.vessels));
      } else if (msg.type === "tracks_batch") {
        setTracks(msg.tracks);
      } else if (msg.type === "ais") {
        applyAis(msg);
      }
    });
    clientRef.current = client;
    return () => client.close();
  }, [applyAis, mode, speed]);

  const vesselList = useMemo(() => Array.from(vessels.values()), [vessels]);
  const filteredVesselList = useMemo(() => {
    let list = filterVesselsByShipType(vesselList, shipTypeFilter);
    list = filterVesselsByNation(list, nationFilter);
    return list;
  }, [vesselList, shipTypeFilter, nationFilter]);
  const filteredTracks = useMemo(() => {
    if (shipTypeFilter.size === 0 && nationFilter.size === 0) return tracks;
    const visibleMmsis = new Set(filteredVesselList.map((vessel) => vessel.mmsi));
    return tracks.filter((track) => visibleMmsis.has(track.mmsi));
  }, [tracks, filteredVesselList, shipTypeFilter, nationFilter]);
  const selectedVessel = selectedMmsi != null ? vessels.get(selectedMmsi) ?? null : null;
  const send = (payload: Record<string, unknown>) => clientRef.current?.send(payload);

  const isLive = mode === "live" || (scenario != null && current !== "" && toMs(current) >= toMs(scenario.end) - 2000);

  const handleSelectVessel = useCallback((mmsi: number | null) => {
    setSelectedMmsi(mmsi);
  }, []);

  const handleCenterSelected = useCallback(() => {
    if (selectedMmsi == null) return;
    const vessel = vessels.get(selectedMmsi);
    if (!vessel) return;
    setCenterRequest({ lat: vessel.lat, lon: vessel.lon, token: Date.now() });
  }, [selectedMmsi, vessels]);

  return (
    <div className="app">
      <TopBar
        connected={connected}
        playing={playing}
        current={current || scenario?.start || ""}
        scenarioName={scenario?.name}
        vesselCount={filteredVesselList.length}
        trackCount={filteredTracks.length}
        positionCount={positionCount}
        isLive={isLive}
        mode={mode}
        aisConnected={aisConnected}
        onModeChange={switchMode}
      />

      <div
        className={[
          "ops-stage",
          fleetCollapsed ? "ops-stage--fleet-collapsed" : "",
          detailCollapsed ? "ops-stage--detail-collapsed" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <MapView
          vessels={filteredVesselList}
          tracks={filteredTracks}
          sarDetections={sarDetections}
          bbox={scenario?.bbox}
          cables={cables}
          selectedMmsi={selectedMmsi}
          layers={layers}
          onSelectVessel={handleSelectVessel}
          centerRequest={centerRequest}
        />

        <div
          className={`ops-overlay ops-overlay--left${fleetCollapsed ? " ops-overlay--collapsed" : ""}`}
        >
          <FleetPanel
            vessels={vesselList}
            selectedMmsi={selectedMmsi}
            onSelect={setSelectedMmsi}
            onCollapsedChange={setFleetCollapsed}
            shipTypeFilter={shipTypeFilter}
            onShipTypeFilterChange={setShipTypeFilter}
            nationFilter={nationFilter}
            onNationFilterChange={setNationFilter}
          />
        </div>

        <div
          className={`ops-overlay ops-overlay--right${detailCollapsed ? " ops-overlay--collapsed" : ""}`}
        >
          <VesselDetail
            vessel={selectedVessel}
            alerts={alerts}
            onCenter={handleCenterSelected}
            onCollapsedChange={setDetailCollapsed}
          />
        </div>

        <div className="ops-overlay ops-overlay--top-right">
          <LayerToggles layers={layers} onChange={setLayers} />
        </div>

        {mode === "live" && (
          <div className="ops-overlay ops-overlay--bottom-left">
            <EventFeed events={alerts} onSelectMmsi={setSelectedMmsi} />
          </div>
        )}

        {connected && mode === "replay" && positionCount === 0 && (
          <div className="empty-banner">
            <strong>No contacts in area of interest</strong>
            Load corridor traffic:
            <code>python scripts/load_live_ais.py --clear</code>
            Or switch to live mode for AISStream ingest.
          </div>
        )}

        {connected && mode === "live" && !aisConnected && (
          <div className="empty-banner">
            <strong>AISStream not connected</strong>
            Set <code>AISSTREAM_API_KEY</code> in the backend environment and restart.
          </div>
        )}
      </div>

      {mode === "replay" && scenario && (
        <TimelineDock
          playing={playing}
          current={current || scenario.end}
          start={scenario.start}
          end={scenario.end}
          dataStart={scenario.dataStart}
          dataEnd={scenario.dataEnd}
          windowPreset={windowPreset}
          windowPresets={WINDOW_PRESETS}
          speed={speed}
          onPlay={() => send({ action: "play" })}
          onPause={() => send({ action: "pause" })}
          onSeek={(t) => send({ action: "seek", t })}
          onWindowPreset={(preset) => {
            setWindowPreset(preset);
            send({ action: "set_window", preset });
          }}
          onSpeed={(multiplier) => {
            setSpeed(multiplier);
            send({ action: "speed", multiplier });
          }}
        />
      )}
    </div>
  );
}
