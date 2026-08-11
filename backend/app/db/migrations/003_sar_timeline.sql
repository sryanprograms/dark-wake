CREATE TABLE IF NOT EXISTS sar_scene (
    id BIGSERIAL PRIMARY KEY,
    scene_id TEXT NOT NULL,
    t TIMESTAMPTZ NOT NULL UNIQUE,
    detection_count INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_sar_scene_t ON sar_scene (t);

CREATE TABLE IF NOT EXISTS sar_detection (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    t TIMESTAMPTZ NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    length_m REAL,
    confidence REAL,
    raw JSONB
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sar_detection_source_t_xy
    ON sar_detection (source, t, (ST_X(geom)), (ST_Y(geom)));
CREATE INDEX IF NOT EXISTS ix_sar_detection_geom ON sar_detection USING GIST (geom);
CREATE INDEX IF NOT EXISTS ix_sar_detection_t ON sar_detection (t);

CREATE TABLE IF NOT EXISTS contact (
    id BIGSERIAL PRIMARY KEY,
    sar_detection_id BIGINT REFERENCES sar_detection(id),
    scene_id BIGINT REFERENCES sar_scene(id),
    classification TEXT NOT NULL,
    matched_mmsi BIGINT,
    match_distance_m REAL,
    match_dt_s REAL,
    predicted_from_gap BOOLEAN NOT NULL DEFAULT FALSE,
    suspicion REAL,
    reason TEXT,
    details JSONB,
    t TIMESTAMPTZ,
    geom GEOMETRY(Point, 4326)
);

CREATE INDEX IF NOT EXISTS ix_contact_geom ON contact USING GIST (geom);
CREATE INDEX IF NOT EXISTS ix_contact_scene_id ON contact (scene_id);
