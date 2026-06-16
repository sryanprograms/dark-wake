export type LayerVisibility = {
  vessels: boolean;
  tracks: boolean;
  corridor: boolean;
  cables: boolean;
  sar: boolean;
};

export const DEFAULT_LAYERS: LayerVisibility = {
  vessels: true,
  tracks: true,
  corridor: true,
  cables: true,
  sar: true,
};
