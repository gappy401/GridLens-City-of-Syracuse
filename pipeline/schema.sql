-- pipeline/schema.sql
-- Run once on a fresh PostgreSQL + PostGIS database.
-- Docker Compose mounts this as an init script automatically.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- fuzzy name search
CREATE EXTENSION IF NOT EXISTS pg_cron;   -- scheduled materialized view refresh (RDS supports this)

-- ── PROJECTS ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id                      SERIAL PRIMARY KEY,
    name                    TEXT,
    fuel_type               TEXT,
    capacity_mw             NUMERIC(10, 2),
    state                   CHAR(2),
    county                  TEXT,
    install_date            DATE,
    source                  TEXT,                          -- 'lbnl' | 'egrid'
    nearest_substation_id   INT,                           -- FK added after substations load
    substation_dist_km      NUMERIC(8, 3),
    geom                    GEOMETRY(POINT, 4326) NOT NULL
);

-- Spatial index: essential for ST_DWithin, bbox &&, KNN (<->)
CREATE INDEX IF NOT EXISTS idx_projects_geom
    ON projects USING GIST (geom);

-- BRIN index: tiny overhead for append-only date column
CREATE INDEX IF NOT EXISTS idx_projects_date
    ON projects USING BRIN (install_date);

-- Scalar filter indexes
CREATE INDEX IF NOT EXISTS idx_projects_state      ON projects (state);
CREATE INDEX IF NOT EXISTS idx_projects_fuel_type  ON projects (fuel_type);
CREATE INDEX IF NOT EXISTS idx_projects_source     ON projects (source);


-- ── SUBSTATIONS ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS substations (
    id          SERIAL PRIMARY KEY,
    name        TEXT,
    voltage_kv  NUMERIC(6, 1),
    owner       TEXT,
    state       CHAR(2),
    geom        GEOMETRY(POINT, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_substations_geom
    ON substations USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_substations_voltage
    ON substations (voltage_kv);


-- ── TRANSMISSION LINES ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transmission_lines (
    id          SERIAL PRIMARY KEY,
    voltage_kv  NUMERIC(6, 1),
    owner       TEXT,
    state       CHAR(2),
    geom        GEOMETRY(LINESTRING, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lines_geom
    ON transmission_lines USING GIST (geom);


-- ── SITING SCORES ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS project_scores (
    id                  SERIAL PRIMARY KEY,
    project_id          INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    score_total         NUMERIC(5, 1),
    score_substation    NUMERIC(5, 1),
    score_voltage       NUMERIC(5, 1),
    score_competition   NUMERIC(5, 1),
    score_land_use      NUMERIC(5, 1),
    score_slope         NUMERIC(5, 1),
    excluded            BOOLEAN DEFAULT FALSE,
    exclusion_reason    TEXT,
    scored_at           TIMESTAMPTZ DEFAULT NOW()
);

-- Partial index: dashboard only ever queries non-excluded high scores
CREATE INDEX IF NOT EXISTS idx_scores_high
    ON project_scores (score_total DESC)
    WHERE excluded = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS idx_scores_project_id
    ON project_scores (project_id);


-- ── FK: add after both tables exist ──────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_projects_substation'
    ) THEN
        ALTER TABLE projects
            ADD CONSTRAINT fk_projects_substation
            FOREIGN KEY (nearest_substation_id)
            REFERENCES substations(id);
    END IF;
END $$;


-- ── MATERIALIZED VIEW: state capacity summary ─────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS state_capacity_summary AS
SELECT
    p.state,
    p.fuel_type,
    COUNT(*)::INT                    AS project_count,
    SUM(p.capacity_mw)::NUMERIC(12,1) AS total_mw,
    AVG(ps.score_total)::NUMERIC(5,1) AS avg_score
FROM projects p
JOIN project_scores ps ON ps.project_id = p.id
WHERE ps.excluded = FALSE
GROUP BY p.state, p.fuel_type;

CREATE UNIQUE INDEX IF NOT EXISTS idx_state_summary
    ON state_capacity_summary (state, fuel_type);

-- Refresh every 6 hours (requires pg_cron extension on RDS)
-- SELECT cron.schedule('refresh-state-summary', '0 */6 * * *',
--   'REFRESH MATERIALIZED VIEW CONCURRENTLY state_capacity_summary');


-- ── HELPER: nearest substation enrichment query ───────────────────────────
-- Run this after ingest.py has loaded both projects and substations.
-- Uses KNN operator (<->) with LATERAL for O(n log n) performance.
--
-- UPDATE projects p
-- SET nearest_substation_id = nearest.sub_id,
--     substation_dist_km = nearest.dist_km
-- FROM (
--     SELECT DISTINCT ON (p2.id)
--         p2.id AS proj_id,
--         s.id  AS sub_id,
--         ST_Distance(p2.geom::geography, s.geom::geography) / 1000.0 AS dist_km
--     FROM projects p2
--     CROSS JOIN LATERAL (
--         SELECT id, geom
--         FROM substations
--         ORDER BY substations.geom <-> p2.geom
--         LIMIT 1
--     ) s
-- ) nearest
-- WHERE p.id = nearest.proj_id;
