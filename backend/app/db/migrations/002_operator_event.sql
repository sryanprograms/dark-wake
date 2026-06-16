CREATE TABLE IF NOT EXISTS operator_event (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL,
    mmsi BIGINT,
    t TIMESTAMPTZ NOT NULL,
    title TEXT NOT NULL,
    reason TEXT,
    details JSONB,
    geom GEOMETRY(Point, 4326),
    track_excerpt JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_operator_event_t ON operator_event (t DESC);
CREATE INDEX IF NOT EXISTS ix_operator_event_kind ON operator_event (kind);
CREATE INDEX IF NOT EXISTS ix_operator_event_geom ON operator_event USING GIST (geom);
