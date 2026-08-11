import type { SceneContact } from "../ws/timeline";

type AisPoint = { mmsi: number; lat: number; lon: number };

type RawContact = {
  id?: number | string;
  sar_detection_id?: number;
  classification?: string;
  kind?: string;
  lat?: number;
  lon?: number;
  sar_lat?: number;
  sar_lon?: number;
  ais_lat?: number | null;
  ais_lon?: number | null;
  matched_mmsi?: number | null;
  mmsi?: number | null;
  match_distance_m?: number | null;
  distance_m?: number | null;
  suspicion?: number | null;
  confidence?: number | null;
};

export function normalizeSceneContacts(
  raw: RawContact[],
  ais: AisPoint[] = [],
): SceneContact[] {
  const aisByMmsi = new Map(ais.map((v) => [v.mmsi, v]));

  return raw.map((contact) => {
    const kind = (contact.kind ?? contact.classification ?? "dark") as SceneContact["kind"];
    const mmsi = contact.mmsi ?? contact.matched_mmsi ?? null;
    const matched = mmsi != null ? aisByMmsi.get(mmsi) : undefined;
    const sarLat = contact.sar_lat ?? contact.lat ?? 0;
    const sarLon = contact.sar_lon ?? contact.lon ?? 0;

    return {
      id: String(contact.id ?? contact.sar_detection_id ?? `${sarLat},${sarLon}`),
      kind,
      sar_lat: sarLat,
      sar_lon: sarLon,
      ais_lat: contact.ais_lat ?? matched?.lat ?? null,
      ais_lon: contact.ais_lon ?? matched?.lon ?? null,
      mmsi,
      distance_m: contact.distance_m ?? contact.match_distance_m ?? null,
      confidence: contact.confidence ?? contact.suspicion ?? null,
    };
  });
}
