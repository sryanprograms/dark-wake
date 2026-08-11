import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchTimelineBounds, fetchTimelineScenes } from "./api/timeline";
import { fetchCables, type CableSegment } from "./api/cables";
import { EventFeed } from "./components/EventFeed";
import { FleetPanel } from "./components/FleetPanel";
import { LayerToggles } from "./components/LayerToggles";
import { MapLegend } from "./components/MapLegend";
import { SceneContactFeed } from "./components/SceneContactFeed";
import { TimelineDock } from "./components/TimelineDock";
import { TopBar } from "./components/TopBar";
import { VesselDetail } from "./components/VesselDetail";
import { MapView, VesselPoint, VesselTrack } from "./map/MapView";
import { DEFAULT_LAYERS, LayerVisibility } from "./types/layers";
import { countAttentionAlerts } from "./utils/alerts";
import { filterVessels } from "./utils/vesselFilters";
import { normalizeSceneContacts } from "./utils/sceneContacts";
import { emptyMapCopy, resolveEmptyMapState } from "./utils/timelineCoverage";
import { toMs } from "./utils/time";
import {
  AlertEvent,
  AisEvent,
  connectTimeline,
  PlayheadMode,
  SceneContact,
  TimelineMessage,
  TimelineScene,
} from "./ws/timeline";

type Corridor = {
  id: string;
  name: string;
  dataStart: string;
  dataEnd: string;
  liveEdge: string;
  bbox: {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
  };
};

import { DEFAULT_BBOX, LIVE_EDGE_MS } from "./constants/timeline";

function defaultCorridor(): Corridor {
  const now = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 3_600_000);
  const iso = now.toISOString();
  return {
    id: "timeline",
    name: "Danish Belt",
    dataStart: weekAgo.toISOString(),
    dataEnd: iso,
    liveEdge: iso,
    bbox: DEFAULT_BBOX,
  };
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

export default function App() {
  const clientRef = useRef<ReturnType<typeof connectTimeline> | null>(null);
  const playheadModeRef = useRef<PlayheadMode>("live");
  const lastAisAtRef = useRef(0);
  const [vessels, setVessels] = useState<Map<number, VesselPoint>>(new Map());
  const [tracks, setTracks] = useState<VesselTrack[]>([]);
  const [sarDetections, setSarDetections] = useState<
    { id: string; lat: number; lon: number; t?: string; length_m?: number | null }[]
  >([]);
  const [contacts, setContacts] = useState<SceneContact[]>([]);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [corridor, setCorridor] = useState<Corridor | null>(defaultCorridor);
  const [playheadMode, setPlayheadMode] = useState<PlayheadMode>("live");
  const [scenes, setScenes] = useState<TimelineScene[]>([]);
  const [currentSceneId, setCurrentSceneId] = useState<string | null>(null);
  const [current, setCurrent] = useState("");
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const [connected, setConnected] = useState(false);
  const [aisConnected, setAisConnected] = useState(false);
  const [aisReceiving, setAisReceiving] = useState(false);
  const [positionCount, setPositionCount] = useState<number | null>(null);
  const [sceneCount, setSceneCount] = useState<number | null>(null);
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
  const [searchQuery, setSearchQuery] = useState("");
  const [movingOnly, setMovingOnly] = useState(false);

  const applyAis = useCallback((msg: AisEvent | Omit<AisEvent, "type">) => {
    if (playheadModeRef.current === "scene") return;
    setVessels((prev) => {
      const next = new Map(prev);
      next.set(msg.mmsi, aisToVessel(msg));
      return next;
    });
  }, []);

  useEffect(() => {
    playheadModeRef.current = playheadMode;
  }, [playheadMode]);

  useEffect(() => {
    if (playheadMode !== "live" || !connected) {
      setAisReceiving(false);
      return;
    }
    const id = window.setInterval(() => {
      setAisReceiving(Date.now() - lastAisAtRef.current < 60_000);
    }, 2000);
    return () => window.clearInterval(id);
  }, [playheadMode, connected]);

  useEffect(() => {
    if (playheadMode !== "live" || !connected) return;
    const id = window.setInterval(() => {
      setCurrent(new Date().toISOString());
    }, 1000);
    return () => window.clearInterval(id);
  }, [playheadMode, connected]);

  const clearSceneOverlay = useCallback(() => {
    setSarDetections([]);
    setContacts([]);
    setCurrentSceneId(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchTimelineBounds(), fetchTimelineScenes()]).then(([bounds, sceneList]) => {
      if (cancelled) return;
      if (sceneList.length > 0) setScenes(sceneList);
      if (bounds) {
        setPositionCount(bounds.ais_count ?? null);
        setSceneCount(bounds.scene_count ?? null);
        setCorridor((prev) => ({
          id: "timeline",
          name: prev?.name ?? "Danish Belt",
          dataStart: bounds.data_start ?? prev?.dataStart ?? bounds.live_edge,
          dataEnd: bounds.data_end ?? prev?.dataEnd ?? bounds.live_edge,
          liveEdge: bounds.live_edge,
          bbox: prev?.bbox ?? DEFAULT_BBOX,
        }));
        setCurrent((prev) => prev || bounds.live_edge);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchCables(corridor?.bbox)
      .then((segments) => {
        if (!cancelled) setCables(segments);
      })
      .catch(() => {
        if (!cancelled) setCables([]);
      });
    return () => {
      cancelled = true;
    };
  }, [corridor?.bbox]);

  useEffect(() => {
    clientRef.current?.close();
    setConnected(false);
    setVessels(new Map());
    setTracks([]);
    clearSceneOverlay();
    setAlerts([]);
    setSelectedMmsi(null);
    setPlaying(false);

    const client = connectTimeline(`${wsBaseUrl()}/ws/timeline`, (msg: TimelineMessage) => {
      if (msg.type === "timeline_state") {
        setPlayheadMode(msg.mode);
        setCurrent(msg.current ?? msg.playhead ?? "");
        setPlaying(msg.playing ?? false);
        if (msg.speed != null) setSpeed(msg.speed);
        if (msg.scenes?.length) {
          setScenes(msg.scenes);
          setSceneCount(msg.scenes.length);
        }
        setCurrentSceneId(msg.current_scene_id ?? null);
        setPositionCount(msg.position_count ?? msg.vessel_count ?? null);
        setAisConnected(msg.ais_connected ?? false);
        setConnected(true);
        setCorridor({
          id: msg.id ?? "timeline",
          name: msg.name ?? "Danish Belt",
          dataStart: msg.data_start,
          dataEnd: msg.data_end,
          liveEdge: msg.live_edge,
          bbox: msg.bbox ?? DEFAULT_BBOX,
        });
        if (msg.mode !== "scene") clearSceneOverlay();
      } else if (msg.type === "state") {
        setCurrent(msg.current);
        setPlaying(msg.playing);
        if (msg.mode) {
          setPlayheadMode(msg.mode);
          if (msg.mode !== "scene") clearSceneOverlay();
        }
        if (msg.current_scene_id !== undefined) {
          setCurrentSceneId(msg.current_scene_id);
        }
      } else if (msg.type === "ais_batch") {
        if (playheadModeRef.current !== "scene") {
          if (msg.source !== "db_snapshot") {
            lastAisAtRef.current = Date.now();
            setAisReceiving(true);
          }
          setVessels(vesselsFromBatch(msg.vessels));
        }
      } else if (msg.type === "tracks_batch") {
        if (playheadModeRef.current !== "scene") {
          setTracks(msg.tracks);
        }
      } else if (msg.type === "ais") {
        applyAis(msg);
        if (playheadModeRef.current !== "scene") {
          lastAisAtRef.current = Date.now();
          setAisReceiving(true);
          setCurrent(msg.t);
        }
      } else if (msg.type === "scene_frame") {
        playheadModeRef.current = "scene";
        setPlayheadMode("scene");
        setCurrent(msg.t);
        setCurrentSceneId(String(msg.scene_id));
        setSarDetections(
          msg.sar.map((d) => ({
            ...d,
            id: String(d.id),
          })),
        );
        const aisPoints = (msg.ais ?? []).map((v) => ({
          mmsi: v.mmsi,
          lat: v.lat,
          lon: v.lon,
        }));
        setContacts(normalizeSceneContacts(msg.contacts, aisPoints));
        setVessels(vesselsFromBatch(msg.ais ?? []));
        setTracks(msg.tracks ?? []);
      } else if (msg.type === "alert") {
        setAlerts((prev) => [msg, ...prev].slice(0, 100));
      }
    });
    clientRef.current = client;
    return () => client.close();
  }, [applyAis, clearSceneOverlay]);

  const vesselList = useMemo(() => Array.from(vessels.values()), [vessels]);
  const filteredVesselList = useMemo(
    () =>
      filterVessels(vesselList, {
        shipTypeFilter,
        nationFilter,
        searchQuery,
        movingOnly,
      }),
    [vesselList, shipTypeFilter, nationFilter, searchQuery, movingOnly],
  );
  const filteredTracks = useMemo(() => {
    if (
      shipTypeFilter.size === 0 &&
      nationFilter.size === 0 &&
      !searchQuery.trim() &&
      !movingOnly
    ) {
      return tracks;
    }
    const visibleMmsis = new Set(filteredVesselList.map((vessel) => vessel.mmsi));
    return tracks.filter((track) => visibleMmsis.has(track.mmsi));
  }, [tracks, filteredVesselList, shipTypeFilter, nationFilter, searchQuery, movingOnly]);
  const attentionCount = useMemo(() => countAttentionAlerts(alerts), [alerts]);
  const selectedVessel = selectedMmsi != null ? vessels.get(selectedMmsi) ?? null : null;
  const client = () => clientRef.current;

  const handleCenterSelected = useCallback(() => {
    if (selectedMmsi == null) return;
    const vessel = vessels.get(selectedMmsi);
    if (!vessel) return;
    setCenterRequest({ lat: vessel.lat, lon: vessel.lon, token: Date.now() });
  }, [selectedMmsi, vessels]);

  const handleClearFilters = useCallback(() => {
    setShipTypeFilter(new Set());
    setNationFilter(new Set());
    setSearchQuery("");
    setMovingOnly(false);
  }, []);

  const dataStart = corridor?.dataStart ?? current;
  const liveEdge = corridor?.liveEdge ?? current;
  const dataEnd = corridor?.dataEnd ?? liveEdge;

  const emptyMapState = useMemo(
    () =>
      resolveEmptyMapState({
        connected,
        playheadMode,
        vesselCount: vesselList.length,
        aisConnected,
        positionCount,
        dataStart,
        liveEdge,
        sarDetectionCount: sarDetections.length,
      }),
    [
      connected,
      playheadMode,
      vesselList.length,
      aisConnected,
      positionCount,
      dataStart,
      liveEdge,
      sarDetections.length,
    ],
  );
  const emptyMapMessage = useMemo(() => emptyMapCopy(emptyMapState), [emptyMapState]);

  const handleSeek = useCallback(
    (t: string) => {
      const targetMs = toMs(t);
      const liveMs = toMs(liveEdge);
      const endMs = toMs(dataEnd);
      if (liveMs - targetMs <= LIVE_EDGE_MS) {
        clientRef.current?.goLive();
      } else if (targetMs > endMs) {
        clientRef.current?.goLive();
      } else {
        clientRef.current?.seek(t);
      }
    },
    [dataEnd, liveEdge],
  );

  const handlePlay = useCallback(() => {
    if (playheadMode === "live") {
      clientRef.current?.seek(dataEnd);
      window.setTimeout(() => clientRef.current?.play(), 50);
      return;
    }
    clientRef.current?.play();
  }, [dataEnd, playheadMode]);

  return (
    <div className="app">
      <TopBar
        connected={connected}
        current={current || liveEdge}
        scenarioName={corridor?.name}
        dataStart={dataStart}
        liveEdge={liveEdge}
        vesselCount={filteredVesselList.length}
        attentionCount={attentionCount}
        trackCount={filteredTracks.length}
        positionCount={positionCount}
        sceneCount={sceneCount}
        playheadMode={playheadMode}
        aisConnected={aisConnected}
        aisReceiving={aisReceiving}
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
          sarDetections={playheadMode === "scene" ? sarDetections : []}
          contacts={playheadMode === "scene" ? contacts : []}
          bbox={corridor?.bbox}
          cables={cables}
          selectedMmsi={selectedMmsi}
          layers={layers}
          onSelectVessel={setSelectedMmsi}
          centerRequest={centerRequest}
        />

        <div
          className={`ops-overlay ops-overlay--left${fleetCollapsed ? " ops-overlay--collapsed" : ""}`}
        >
          <FleetPanel
            vessels={filteredVesselList}
            allVessels={vesselList}
            selectedMmsi={selectedMmsi}
            onSelect={setSelectedMmsi}
            onCollapsedChange={setFleetCollapsed}
            shipTypeFilter={shipTypeFilter}
            onShipTypeFilterChange={setShipTypeFilter}
            nationFilter={nationFilter}
            onNationFilterChange={setNationFilter}
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
            movingOnly={movingOnly}
            onMovingOnlyChange={setMovingOnly}
            onClearFilters={handleClearFilters}
            referenceTime={current || dataStart}
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
            referenceTime={current || dataStart}
          />
        </div>

        <div className="ops-overlay ops-overlay--top-right">
          <LayerToggles layers={layers} playheadMode={playheadMode} onChange={setLayers} />
        </div>

        <div className="ops-overlay ops-overlay--bottom-right">
          <MapLegend />
        </div>

        <div className="ops-overlay ops-overlay--bottom-left">
          {playheadMode === "scene" ? (
            <SceneContactFeed
              contacts={contacts}
              sceneTime={current}
              onSelectMmsi={setSelectedMmsi}
            />
          ) : (
            <EventFeed events={alerts} onSelectMmsi={setSelectedMmsi} />
          )}
        </div>

        {emptyMapMessage ? (
          <div className="empty-banner">
            <strong>{emptyMapMessage.title}</strong>
            {emptyMapMessage.body}
          </div>
        ) : null}
      </div>

      <TimelineDock
        playing={playing}
        current={current || liveEdge}
        dataStart={dataStart}
        liveEdge={liveEdge}
        playheadMode={playheadMode}
        scenes={scenes}
        currentSceneId={currentSceneId}
        positionCount={positionCount}
        speed={speed}
        onPlay={handlePlay}
        onPause={() => client()?.pause()}
        onSeek={handleSeek}
        onGoLive={() => client()?.goLive()}
        onSceneClick={(sceneId) => client()?.snapScene(sceneId)}
        onSpeed={(multiplier) => {
          setSpeed(multiplier);
          client()?.speed(multiplier);
        }}
      />
    </div>
  );
}
