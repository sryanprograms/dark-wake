"""Area of interest configuration — bbox is a parameter, not hard-coded logic."""

# Gulf of Finland cable corridor (primary demo AOI per spec §4).
# min_lat expanded to 58.5°N after Phase 0 spike: GFW SAR detections cluster in the
# approach waters south of 59.3°N; the cable corridor (59.3–60.3°N) stays inside.
AOI_NAME = "gulf_of_finland"
BBOX = {
    "min_lat": 58.5,
    "max_lat": 60.3,
    "min_lon": 23.0,
    "max_lon": 27.0,
}

# Wider polygon for GFW API queries — the tight bbox alone can return null rows.
GFW_QUERY_BBOX = {
    "min_lat": 58.0,
    "max_lat": 61.0,
    "min_lon": 22.0,
    "max_lon": 28.5,
}

# Window with confirmed GFW SAR coverage in this AOI (Phase 0 spike, 2022-06).
DEFAULT_START = "2022-06-01T00:00:00Z"
DEFAULT_END = "2022-06-30T00:00:00Z"


def _ring(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> list[list[float]]:
    return [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]


def bbox_polygon_coords() -> list[list[float]]:
    """GeoJSON polygon ring (lon, lat) for the AOI bbox."""
    return _ring(BBOX["min_lon"], BBOX["min_lat"], BBOX["max_lon"], BBOX["max_lat"])


def gfw_query_polygon_coords() -> list[list[float]]:
    """GeoJSON polygon for GFW SAR pulls; results are filtered back to BBOX."""
    return _ring(
        GFW_QUERY_BBOX["min_lon"],
        GFW_QUERY_BBOX["min_lat"],
        GFW_QUERY_BBOX["max_lon"],
        GFW_QUERY_BBOX["max_lat"],
    )
