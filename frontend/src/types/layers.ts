export type LayerVisibility = {
  vessels: boolean;
  tracks: boolean;
  corridor: boolean;
  cables: boolean;
};

export const DEFAULT_LAYERS: LayerVisibility = {
  vessels: true,
  tracks: true,
  corridor: true,
  cables: true,
};
