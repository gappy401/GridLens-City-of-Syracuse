"""
pipeline/score.py
-----------------
Siting score engine for the Renewable Project Atlas.

Computes a 0–100 composite siting score for every project
across 6 dimensions, then writes results to the project_scores table.

Dimensions and weights:
  substation_dist  30%  (100 at 0km, linear decay to 0 at 25km)
  voltage          25%  (345kV+=100, 230kV=70, 115kV=40, <115kV=10)
  competition      15%  (inverse sigmoid on queue density / projects per km²)
  land_use         15%  (NLCD code mapping)
  slope            15%  (solar: <3°=100; wind optimised separately)
  exclusion        hard  (wetlands / protected / FEMA flood → score=0)

Usage:
  python pipeline/score.py
  python pipeline/score.py --project-id 4821   # score a single project
"""

import argparse
import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text

from config import settings

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")


# ── Score dimension dataclass ─────────────────────────────────────────────────

@dataclass
class SitingScore:
    project_id: int
    fuel_type: str = "Solar"

    # Raw inputs
    substation_dist_km: float = 999.0
    nearest_voltage_kv: float = 0.0
    queue_density: float = 0.0      # competing projects per km² within 50km
    land_use_code: int = 0          # NLCD 2021 code
    slope_deg: float = 0.0
    in_exclusion_zone: bool = False  # wetland | protected | FEMA flood

    # Computed sub-scores (populated by properties)
    _scores: dict = field(default_factory=dict, init=False, repr=False)

    # ── Sub-score properties ───────────────────────────────────────────────

    @property
    def score_substation(self) -> float:
        """Linear decay: 100 at 0 km → 0 at 25 km."""
        return round(max(0.0, 100.0 - (self.substation_dist_km / 25.0) * 100.0), 1)

    @property
    def score_voltage(self) -> float:
        """Step function on nearest high-voltage line."""
        kv = self.nearest_voltage_kv
        if kv >= 345:  return 100.0
        if kv >= 230:  return 70.0
        if kv >= 115:  return 40.0
        if kv >= 69:   return 20.0
        return 10.0

    @property
    def score_competition(self) -> float:
        """Inverse sigmoid: fewer competing projects nearby = higher score."""
        return round(100.0 / (1.0 + self.queue_density * 5.0), 1)

    @property
    def score_land_use(self) -> float:
        """NLCD 2021 code → suitability score."""
        nlcd_map = {
            81: 90, 82: 90,   # pasture / crops
            31: 80,            # barren land
            52: 70, 51: 70,   # shrub/scrub
            71: 65,            # grassland
            41: 30, 42: 30, 43: 30,  # forest
            21: 20,            # developed open
            22: 10, 23: 5, 24: 0,    # developed medium–high intensity
            11: 0,             # open water
            90: 0, 95: 0,     # woody / emergent wetlands (exclusion)
        }
        return float(nlcd_map.get(self.land_use_code, 50))

    @property
    def score_slope(self) -> float:
        """
        Solar: flat land preferred (<3°=100).
        Wind:  moderate slope preferred (5–15°=90).
        """
        deg = self.slope_deg
        if self.fuel_type.lower() in ("wind", "offshore wind"):
            if 5 <= deg <= 15:  return 90.0
            if 3 <= deg < 5:    return 70.0
            if deg < 3:         return 50.0
            if deg <= 25:       return 30.0
            return 0.0
        else:  # solar
            if deg < 3:    return 100.0
            if deg < 8:    return 70.0
            if deg < 15:   return 30.0
            return 0.0

    # ── Composite score ────────────────────────────────────────────────────

    WEIGHTS = {
        "substation":  0.30,
        "voltage":     0.25,
        "competition": 0.15,
        "land_use":    0.15,
        "slope":       0.15,
    }

    def total(self) -> float:
        if self.in_exclusion_zone:
            return 0.0
        raw = (
            self.WEIGHTS["substation"]  * self.score_substation  +
            self.WEIGHTS["voltage"]     * self.score_voltage      +
            self.WEIGHTS["competition"] * self.score_competition  +
            self.WEIGHTS["land_use"]    * self.score_land_use     +
            self.WEIGHTS["slope"]       * self.score_slope
        )
        return round(raw, 1)

    def breakdown(self) -> dict:
        return {
            "project_id":          self.project_id,
            "score_total":         self.total(),
            "score_substation":    self.score_substation,
            "score_voltage":       self.score_voltage,
            "score_competition":   self.score_competition,
            "score_land_use":      self.score_land_use,
            "score_slope":         self.score_slope,
            "excluded":            self.in_exclusion_zone,
            "exclusion_reason":    "exclusion_zone" if self.in_exclusion_zone else None,
        }


# ── Fetch project rows from DB ────────────────────────────────────────────────

FETCH_SQL = text("""
SELECT
    p.id,
    p.fuel_type,
    p.substation_dist_km,
    s.voltage_kv                           AS nearest_voltage_kv,
    -- Competition: projects within 50km radius / area in km²
    (
        SELECT COUNT(*) / (PI() * 50.0 * 50.0)
        FROM projects p2
        WHERE ST_DWithin(p.geom::geography, p2.geom::geography, 50000)
          AND p2.id != p.id
    )                                      AS queue_density,
    -- Land use code (NLCD) — stored in projects if available, else default 82 (crops)
    COALESCE(p.land_use_code, 82)          AS land_use_code,
    -- Slope in degrees — stored after DEM raster extraction, else default 2
    COALESCE(p.slope_deg, 2.0)             AS slope_deg,
    -- Exclusion: project intersects wetlands / protected areas / flood zone
    COALESCE(p.in_exclusion_zone, FALSE)   AS in_exclusion_zone
FROM projects p
LEFT JOIN substations s ON s.id = p.nearest_substation_id
:where_clause
ORDER BY p.id
""")


def fetch_project_inputs(engine, project_id: Optional[int] = None) -> pd.DataFrame:
    where = "WHERE p.id = :pid" if project_id else ""
    sql = text(FETCH_SQL.text.replace(":where_clause", where))
    params = {"pid": project_id} if project_id else {}
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params=params)
    log.info("Fetched %d project rows for scoring", len(df))
    return df


# ── Write scores to DB ────────────────────────────────────────────────────────

UPSERT_SQL = text("""
INSERT INTO project_scores
    (project_id, score_total, score_substation, score_voltage,
     score_competition, score_land_use, score_slope, excluded, exclusion_reason, scored_at)
VALUES
    (:project_id, :score_total, :score_substation, :score_voltage,
     :score_competition, :score_land_use, :score_slope, :excluded, :exclusion_reason, NOW())
ON CONFLICT (project_id) DO UPDATE SET
    score_total       = EXCLUDED.score_total,
    score_substation  = EXCLUDED.score_substation,
    score_voltage     = EXCLUDED.score_voltage,
    score_competition = EXCLUDED.score_competition,
    score_land_use    = EXCLUDED.score_land_use,
    score_slope       = EXCLUDED.score_slope,
    excluded          = EXCLUDED.excluded,
    exclusion_reason  = EXCLUDED.exclusion_reason,
    scored_at         = EXCLUDED.scored_at
""")


def write_scores(scores: list[dict], engine) -> None:
    with engine.connect() as conn:
        conn.execute(UPSERT_SQL, scores)
        conn.commit()
    log.info("Upserted %d scores", len(scores))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compute siting scores")
    parser.add_argument("--project-id", type=int, default=None,
                        help="Score a single project by ID")
    args = parser.parse_args()

    engine = create_engine(settings.DATABASE_URL)
    df = fetch_project_inputs(engine, project_id=args.project_id)

    if df.empty:
        log.warning("No projects found to score.")
        return

    scores = []
    for _, row in df.iterrows():
        s = SitingScore(
            project_id=int(row["id"]),
            fuel_type=str(row.get("fuel_type", "Solar")),
            substation_dist_km=float(row.get("substation_dist_km") or 999),
            nearest_voltage_kv=float(row.get("nearest_voltage_kv") or 0),
            queue_density=float(row.get("queue_density") or 0),
            land_use_code=int(row.get("land_use_code") or 82),
            slope_deg=float(row.get("slope_deg") or 2),
            in_exclusion_zone=bool(row.get("in_exclusion_zone") or False),
        )
        scores.append(s.breakdown())

    write_scores(scores, engine)

    # Summary stats
    totals = [s["score_total"] for s in scores]
    log.info(
        "Scoring summary: min=%.1f, mean=%.1f, max=%.1f, excluded=%d",
        min(totals), sum(totals) / len(totals), max(totals),
        sum(1 for s in scores if s["excluded"]),
    )
    log.info("✓ Scoring complete. Refresh materialized view if needed.")


if __name__ == "__main__":
    main()
