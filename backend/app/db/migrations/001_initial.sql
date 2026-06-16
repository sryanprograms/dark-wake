CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS vessel (
    mmsi BIGINT PRIMARY KEY,
    imo BIGINT,
    name TEXT,
    callsign TEXT,
    ship_type TEXT,
    length_m REAL,
    width_m REAL,
    flag TEXT,
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ais_position (
    id BIGSERIAL PRIMARY KEY,
    mmsi BIGINT NOT NULL REFERENCES vessel(mmsi),
    t TIMESTAMPTZ NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    sog REAL,
    cog REAL,
    heading REAL,
    nav_status TEXT
);

CREATE INDEX IF NOT EXISTS ix_pos_mmsi_t ON ais_position (mmsi, t);
CREATE INDEX IF NOT EXISTS ix_pos_geom ON ais_position USING GIST (geom);
