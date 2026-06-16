import { useEffect, useMemo, useRef, useState } from "react";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { IconLayer, PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { PickingInfo } from "@deck.gl/core";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  ARROW_ICON_MAPPING,
  getArrowIconAtlas,
  iconAngleFromHeading,
  vesselIconKind,
  vesselIconSize,
} from "./arrowIcon";
import type { CableSegment } from "../api/cables";
import type { LayerVisibility } from "../types/layers";
import { formatUtcShort } from "../utils/time";

export type VesselPoint = {
  mmsi: number;
  lat: number;
  lon: number;
  heading?: number | null;
  sog?: number | null;
  cog?: number | null;
  name?: string | null;
  ship_type?: string | null;
  flag?: string | null;
  country?: string | null;
  t?: string;
};

export type VesselTrack = {
  mmsi: number;
  path: [number, number][];
};

type MapViewProps = {
  vessels: VesselPoint[];
  tracks: VesselTrack[];
  bbox?: {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
  };
  cables?: CableSegment[];
  selectedMmsi: number | null;
  layers: LayerVisibility;
  onSelectVessel: (mmsi: number | null) => void;
  centerRequest?: { lat: number; lon: number; token: number } | null;
};

const DEFAULT_CENTER: [number, number] = [25.0, 59.8];
const DEFAULT_ZOOM = 7;

const DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

function VesselTooltip({ vessel, x, y }: { vessel: VesselPoint; x: number; y: number }) {
  return (
    <div className="vessel-tooltip" style={{ left: x, top: y }}>
      <strong>{vessel.name?.trim() || `MMSI ${vessel.mmsi}`}</strong>
      <div>MMSI {vessel.mmsi}</div>
      <div>SOG {vessel.sog ?? "—"} kn · COG {vessel.cog ?? "—"}°</div>
      <div>Heading {vessel.heading ?? "—"}°</div>
      <div>{vessel.t ? formatUtcShort(vessel.t) : "—"}</div>
    </div>
  );
}

function CableTooltip({ cable, x, y }: { cable: CableSegment; x: number; y: number }) {
  return (
    <div className="vessel-tooltip" style={{ left: x, top: y }}>
      <strong>{cable.name}</strong>
      <div>Submarine cable</div>
    </div>
  );
}

function bboxPath(bbox: NonNullable<MapViewProps["bbox"]>): [number, number][] {
  const { min_lon, min_lat, max_lon, max_lat } = bbox;
  return [
    [min_lon, min_lat],
    [max_lon, min_lat],
    [max_lon, max_lat],
    [min_lon, max_lat],
    [min_lon, min_lat],
  ];
}

export function MapView({
  vessels,
  tracks,
  bbox,
  cables = [],
  selectedMmsi,
  layers,
  onSelectVessel,
  centerRequest,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const pickedRef = useRef(false);
  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<{ vessel: VesselPoint; x: number; y: number } | null>(
    null,
  );
  const [cableHover, setCableHover] = useState<{
    cable: CableSegment;
    x: number;
    y: number;
  } | null>(null);
  const [cursor, setCursor] = useState<{ lat: number; lon: number } | null>(null);

  const iconAtlas = useMemo(() => getArrowIconAtlas(), []);

  const selectedVessel = useMemo(
    () => vessels.find((v) => v.mmsi === selectedMmsi) ?? null,
    [vessels, selectedMmsi],
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: DARK_STYLE,
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      attributionControl: false,
    });

    const overlay = new MapboxOverlay({ interleaved: true });
    map.addControl(overlay as unknown as maplibregl.IControl);
    map.on("load", () => setReady(true));
    map.on("mousemove", (e) => setCursor({ lat: e.lngLat.lat, lon: e.lngLat.lng }));
    map.on("mouseout", () => setCursor(null));
    map.on("click", () => {
      window.setTimeout(() => {
        if (!pickedRef.current) onSelectVessel(null);
        pickedRef.current = false;
      }, 0);
    });

    mapRef.current = map;
    overlayRef.current = overlay;

    return () => {
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!ready || !overlayRef.current || !iconAtlas) return;

    const deckLayers = [];

    if (layers.cables && cables.length > 0) {
      deckLayers.push(
        new PathLayer<CableSegment>({
          id: "submarine-cables",
          data: cables,
          getPath: (d) => d.path,
          getColor: (d) => d.color ?? [255, 170, 60, 210],
          getWidth: 4,
          widthMinPixels: 2,
          widthMaxPixels: 8,
          capRounded: true,
          jointRounded: true,
          pickable: true,
          onHover: (info: PickingInfo<CableSegment>) => {
            if (info.object && info.x != null && info.y != null) {
              setCableHover({ cable: info.object, x: info.x, y: info.y });
            } else {
              setCableHover(null);
            }
          },
        }),
      );
    }

    if (layers.corridor && bbox) {
      deckLayers.push(
        new PathLayer<{ path: [number, number][] }>({
          id: "corridor-bbox",
          data: [{ path: bboxPath(bbox) }],
          getPath: (d) => d.path,
          getColor: [78, 205, 196, 140],
          getWidth: 2,
          widthMinPixels: 2,
          capRounded: false,
          jointRounded: false,
          pickable: false,
        }),
      );
    }

    if (layers.tracks) {
      deckLayers.push(
        new PathLayer<VesselTrack>({
          id: "ais-tracks",
          data: tracks,
          getPath: (d) => d.path,
          getColor: (d) =>
            d.mmsi === selectedMmsi ? [120, 180, 210, 200] : [70, 100, 130, 100],
          getWidth: (d) => (d.mmsi === selectedMmsi ? 3 : 2),
          widthMinPixels: 1,
          widthMaxPixels: 5,
          capRounded: true,
          jointRounded: true,
          pickable: false,
        }),
      );
    }

    if (layers.vessels) {
      if (selectedVessel) {
        deckLayers.push(
          new ScatterplotLayer<VesselPoint>({
            id: "ais-vessel-selection-ring",
            data: [selectedVessel],
            getPosition: (d) => [d.lon, d.lat],
            getRadius: 800,
            radiusMinPixels: 18,
            radiusMaxPixels: 28,
            getFillColor: [78, 205, 196, 30],
            getLineColor: [78, 205, 196, 180],
            lineWidthMinPixels: 2,
            stroked: true,
            filled: true,
            pickable: false,
          }),
        );
      }

      deckLayers.push(
        new IconLayer<VesselPoint>({
          id: "ais-vessels",
          data: vessels,
          iconAtlas,
          iconMapping: ARROW_ICON_MAPPING,
          getIcon: (d) => vesselIconKind(d.sog, d.mmsi === selectedMmsi),
          getPosition: (d) => [d.lon, d.lat],
          getSize: (d) => vesselIconSize(d.sog, d.mmsi === selectedMmsi),
          sizeMinPixels: 10,
          sizeMaxPixels: 30,
          getAngle: (d) => iconAngleFromHeading(d.heading, d.cog, d.sog),
          billboard: false,
          pickable: true,
          onHover: (info: PickingInfo<VesselPoint>) => {
            if (info.object && info.x != null && info.y != null) {
              setHover({ vessel: info.object, x: info.x, y: info.y });
            } else {
              setHover(null);
            }
          },
          onClick: (info: PickingInfo<VesselPoint>) => {
            if (info.object) {
              pickedRef.current = true;
              onSelectVessel(info.object.mmsi);
            }
          },
        }),
      );
    }

    overlayRef.current.setProps({ layers: deckLayers });
  }, [
    ready,
    vessels,
    tracks,
    iconAtlas,
    bbox,
    cables,
    layers,
    selectedMmsi,
    selectedVessel,
    onSelectVessel,
  ]);

  useEffect(() => {
    if (!mapRef.current || !centerRequest) return;
    mapRef.current.flyTo({
      center: [centerRequest.lon, centerRequest.lat],
      zoom: Math.max(mapRef.current.getZoom(), 9),
      duration: 600,
    });
  }, [centerRequest]);

  return (
    <div className="map-container" ref={containerRef}>
      {hover && selectedMmsi !== hover.vessel.mmsi && (
        <VesselTooltip vessel={hover.vessel} x={hover.x + 12} y={hover.y + 12} />
      )}
      {cableHover && (
        <CableTooltip cable={cableHover.cable} x={cableHover.x + 12} y={cableHover.y + 12} />
      )}
      {cursor && (
        <div className="map-hud-coords">
          <span>{cursor.lat.toFixed(4)}°N</span>
          <span>{cursor.lon.toFixed(4)}°E</span>
        </div>
      )}
    </div>
  );
}
