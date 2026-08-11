"""Area of interest configuration — bbox is a parameter, not hard-coded logic."""

# Southern Baltic / Danish Belt (primary demo AOI).
# GFW SAR has reliable coverage here; historical AIS via Danish Maritime Authority (DMA).
AOI_NAME = "danish_belt"
BBOX = {
    "min_lat": 54.8,
    "max_lat": 56.8,
    "min_lon": 10.2,
    "max_lon": 13.2,
}

# Wider polygon for GFW API queries — the tight bbox alone can return null rows.
GFW_QUERY_BBOX = {
    "min_lat": 54.0,
    "max_lat": 57.5,
    "min_lon": 9.5,
    "max_lon": 14.5,
}

# Default pull window — summer week with DMA historical + GFW SAR overlap.
# Override with --start/--end on pull/load scripts for other ranges.
DEFAULT_START = "2024-06-15T00:00:00Z"
DEFAULT_END = "2024-06-22T00:00:00Z"


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


def aisstream_bounding_boxes() -> list[list[list[float]]]:
    """AISStream subscription format: [[[min_lat, min_lon], [max_lat, max_lon]]]."""
    return [[[BBOX["min_lat"], BBOX["min_lon"]], [BBOX["max_lat"], BBOX["max_lon"]]]]


def gfw_query_polygon_coords() -> list[list[float]]:
    """GeoJSON polygon for GFW SAR pulls; results are filtered back to BBOX."""
    return _ring(
        GFW_QUERY_BBOX["min_lon"],
        GFW_QUERY_BBOX["min_lat"],
        GFW_QUERY_BBOX["max_lon"],
        GFW_QUERY_BBOX["max_lat"],
    )
