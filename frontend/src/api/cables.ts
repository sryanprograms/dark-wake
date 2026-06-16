export type CableSegment = {
  id: string;
  cable_id: string;
  name: string;
  path: [number, number][];
  color: [number, number, number, number] | null;
};

type CablesResponse = {
  source: string;
  bbox: {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
  };
  count: number;
  cables: CableSegment[];
};

export async function fetchCables(bbox?: CablesResponse["bbox"]): Promise<CableSegment[]> {
  const params = new URLSearchParams();
  if (bbox) {
    params.set("min_lat", String(bbox.min_lat));
    params.set("max_lat", String(bbox.max_lat));
    params.set("min_lon", String(bbox.min_lon));
    params.set("max_lon", String(bbox.max_lon));
  }
  const query = params.toString();
  const response = await fetch(`/assets/cables${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(`Failed to load cables (${response.status})`);
  }
  const payload = (await response.json()) as CablesResponse;
  return payload.cables;
}
