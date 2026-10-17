-- 001: события и журнал запусков модулей.
CREATE TABLE events (
    id             TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    trace_id       TEXT NOT NULL,
    source         TEXT NOT NULL,
    kind           TEXT NOT NULL,
    entity         TEXT NOT NULL,
    time_ms        INTEGER NOT NULL,   -- когда случилось в мире
    stored_ms      INTEGER NOT NULL,   -- когда Система это узнала
    data           TEXT NOT NULL       -- всё событие целиком, JSON
);
CREATE INDEX events_time ON events (time_ms);
CREATE INDEX events_source_time ON events (source, time_ms);

CREATE TABLE runs (
    id          INTEGER PRIMARY KEY,
    mission     TEXT NOT NULL,
    module      TEXT NOT NULL,         -- "collector:usgs_quakes"
    started_ms  INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    ok          INTEGER NOT NULL,
    n_events    INTEGER NOT NULL,
    error       TEXT
);
CREATE INDEX runs_module ON runs (module, started_ms);
