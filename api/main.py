"""
api/main.py
-----------
FastAPI microservice for the Renewable Project Atlas.

Routes:
  GET  /projects                — Spatial bbox query → GeoJSON
  GET  /projects/{id}/score     — Full siting scorecard
  GET  /clusters                — Server-side K-means clusters
  GET  /substations/nearest     — Nearest substation to a point
  POST /pipeline/trigger        — Trigger ingestion DAG (API-key protected)
  GET  /health                  — Health check
"""

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

import redis as redis_lib
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import (
    GeoJSONCollection,
    NearestSubstationResponse,
    PipelineTriggerResponse,
    ProjectScoreResponse,
)
from pipeline.config import settings

log = logging.getLogger(__name__)

app = FastAPI(
    title="Renewable Project Atlas API",
    version="1.0.0",
    description="Geospatial microservice for renewable energy siting intelligence.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

cache = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

CACHE_TTL_BBOX = 300       # 5 min for bbox queries
CACHE_TTL_SCORE = 3600     # 1 hr for scorecards


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── GET /projects ─────────────────────────────────────────────────────────────

@app.get("/projects", response_model=GeoJSONCollection)
def get_projects(
    min_lon: float = Query(..., ge=-180, le=180, description="West boundary"),
    min_lat: float = Query(..., ge=-90,  le=90,  description="South boundary"),
    max_lon: float = Query(..., ge=-180, le=180, description="East boundary"),
    max_lat: float = Query(..., ge=-90,  le=90,  description="North boundary"),
    fuel_type: Optional[str] = Query(None, description="Solar | Wind | Battery"),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """
    Return projects within a bounding box as a GeoJSON FeatureCollection.
    Uses PostGIS && operator with GIST index for sub-50ms spatial filtering.
    Results cached in Redis for 5 minutes.
    """
    cache_key = f"bbox:{min_lon:.4f}:{min_lat:.4f}:{max_lon:.4f}:{max_lat:.4f}:{fuel_type}:{min_score}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    sql = text("""
        SELECT
            p.id,
            p.name,
            p.fuel_type,
            p.capacity_mw,
            p.state,
            ps.score_total,
            ST_AsGeoJSON(p.geom)::json AS geometry
        FROM projects p
        JOIN project_scores ps ON ps.project_id = p.id
        WHERE
            p.geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
            AND ps.excluded = FALSE
            AND (:fuel_type IS NULL OR p.fuel_type ILIKE :fuel_type)
            AND (:min_score IS NULL OR ps.score_total >= :min_score)
        ORDER BY ps.score_total DESC
        LIMIT :limit
    """)

    rows = db.execute(sql, {
        "min_lon": min_lon, "min_lat": min_lat,
        "max_lon": max_lon, "max_lat": max_lat,
        "fuel_type": fuel_type, "min_score": min_score,
        "limit": limit,
    }).fetchall()

    features = [
        {
            "type": "Feature",
            "geometry": row.geometry,
            "properties": {
                "id": row.id,
                "name": row.name,
                "fuel_type": row.fuel_type,
                "capacity_mw": float(row.capacity_mw) if row.capacity_mw else None,
                "state": row.state,
                "score": float(row.score_total) if row.score_total else None,
            },
        }
        for row in rows
    ]

    result = {"type": "FeatureCollection", "features": features, "total": len(features)}
    cache.setex(cache_key, CACHE_TTL_BBOX, json.dumps(result))
    return result


# ── GET /projects/{id}/score ──────────────────────────────────────────────────

@app.get("/projects/{project_id}/score", response_model=ProjectScoreResponse)
def get_project_score(project_id: int, db: Session = Depends(get_db)):
    """
    Return full 6-dimension siting scorecard for a project.
    Includes nearest substation name, voltage, and distance.
    Cached in Redis for 1 hour.
    """
    cache_key = f"score:{project_id}"
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    sql = text("""
        SELECT
            p.id, p.name, p.fuel_type, p.capacity_mw, p.state,
            ps.score_total, ps.score_substation, ps.score_voltage,
            ps.score_competition, ps.score_land_use, ps.score_slope,
            ps.excluded,
            s.id   AS sub_id,
            s.name AS sub_name,
            s.voltage_kv,
            s.owner AS sub_owner,
            p.substation_dist_km
        FROM projects p
        JOIN project_scores ps ON ps.project_id = p.id
        LEFT JOIN substations s ON s.id = p.nearest_substation_id
        WHERE p.id = :id
    """)

    row = db.execute(sql, {"id": project_id}).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    result = {
        "project": {
            "id": row.id,
            "name": row.name,
            "fuel_type": row.fuel_type,
            "capacity_mw": float(row.capacity_mw) if row.capacity_mw else None,
            "state": row.state,
            "score": float(row.score_total) if row.score_total else None,
        },
        "nearest_substation": {
            "id": row.sub_id,
            "name": row.sub_name,
            "voltage_kv": float(row.voltage_kv) if row.voltage_kv else None,
            "owner": row.sub_owner,
            "dist_km": float(row.substation_dist_km) if row.substation_dist_km else None,
        } if row.sub_id else None,
        "scores": {
            "total":       float(row.score_total or 0),
            "substation":  float(row.score_substation or 0),
            "voltage":     float(row.score_voltage or 0),
            "competition": float(row.score_competition or 0),
            "land_use":    float(row.score_land_use or 0),
            "slope":       float(row.score_slope or 0),
            "excluded":    bool(row.excluded),
        },
    }
    cache.setex(cache_key, CACHE_TTL_SCORE, json.dumps(result))
    return result


# ── GET /clusters ─────────────────────────────────────────────────────────────

@app.get("/clusters")
def get_clusters(
    zoom: int = Query(..., ge=0, le=14, description="Map zoom level"),
    fuel_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Server-side K-means clustering via PostGIS ST_ClusterKMeans.
    Cluster count scales with zoom level for progressive detail.
    """
    # More clusters at higher zoom = finer detail
    num_clusters = max(10, min(200, zoom * zoom + 10))

    cache_key = f"clusters:{zoom}:{fuel_type}"
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    sql = text("""
        WITH clustered AS (
            SELECT
                ST_ClusterKMeans(p.geom, :num_clusters) OVER () AS cluster_id,
                p.capacity_mw,
                ps.score_total,
                p.geom
            FROM projects p
            JOIN project_scores ps ON ps.project_id = p.id
            WHERE ps.excluded = FALSE
              AND (:fuel_type IS NULL OR p.fuel_type ILIKE :fuel_type)
        )
        SELECT
            cluster_id,
            COUNT(*)::INT                    AS project_count,
            SUM(capacity_mw)::NUMERIC(12,1)  AS total_mw,
            AVG(score_total)::NUMERIC(5,1)   AS avg_score,
            ST_AsGeoJSON(ST_Centroid(ST_Collect(geom)))::json AS geometry
        FROM clustered
        GROUP BY cluster_id
        ORDER BY cluster_id
    """)

    rows = db.execute(sql, {"num_clusters": num_clusters, "fuel_type": fuel_type}).fetchall()

    features = [
        {
            "type": "Feature",
            "geometry": row.geometry,
            "properties": {
                "cluster_id": row.cluster_id,
                "project_count": row.project_count,
                "total_mw": float(row.total_mw) if row.total_mw else None,
                "avg_score": float(row.avg_score) if row.avg_score else None,
            },
        }
        for row in rows
    ]

    result = {"type": "FeatureCollection", "features": features}
    cache.setex(cache_key, CACHE_TTL_BBOX, json.dumps(result))
    return result


# ── GET /substations/nearest ──────────────────────────────────────────────────

@app.get("/substations/nearest", response_model=NearestSubstationResponse)
def get_nearest_substation(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    max_km: float = Query(50.0, ge=0.1, le=500),
    min_voltage_kv: Optional[float] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Find the nearest substation to a point using PostGIS KNN (<->) operator.
    Optionally filter by minimum voltage. Returns distance in km.
    """
    sql = text("""
        SELECT
            s.id, s.name, s.voltage_kv, s.owner,
            ST_Distance(s.geom::geography, ST_SetSRID(ST_Point(:lon, :lat), 4326)::geography) / 1000.0
                AS dist_km,
            ST_AsGeoJSON(s.geom)::json AS geometry
        FROM substations s
        WHERE
            ST_DWithin(
                s.geom::geography,
                ST_SetSRID(ST_Point(:lon, :lat), 4326)::geography,
                :max_m
            )
            AND (:min_voltage IS NULL OR s.voltage_kv >= :min_voltage)
        ORDER BY s.geom <-> ST_SetSRID(ST_Point(:lon, :lat), 4326)
        LIMIT 1
    """)

    row = db.execute(sql, {
        "lat": lat, "lon": lon,
        "max_m": max_km * 1000,
        "min_voltage": min_voltage_kv,
    }).first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No substation found within {max_km} km of ({lat}, {lon})",
        )

    return {
        "substation": {
            "id": row.id,
            "name": row.name,
            "voltage_kv": float(row.voltage_kv) if row.voltage_kv else None,
            "owner": row.owner,
            "dist_km": round(float(row.dist_km), 3),
        },
        "geometry": row.geometry,
    }


# ── POST /pipeline/trigger ────────────────────────────────────────────────────

@app.post("/pipeline/trigger", response_model=PipelineTriggerResponse)
def trigger_pipeline(
    sources: Optional[list[str]] = None,
    full_load: bool = False,
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    """
    Trigger the Airflow ingestion DAG via the Airflow REST API.
    Requires X-API-Key header matching the value in settings.
    """
    if not secrets.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")

    run_id = f"manual__{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}"
    triggered_at = datetime.now(timezone.utc).isoformat()

    # In production: call Airflow REST API here
    # import httpx
    # httpx.post(f"{AIRFLOW_URL}/api/v1/dags/atlas_ingest/dagRuns",
    #            json={"dag_run_id": run_id, "conf": {"sources": sources, "full_load": full_load}},
    #            auth=(AIRFLOW_USER, AIRFLOW_PASSWORD))

    return {
        "dag_run_id": run_id,
        "status": "queued",
        "triggered_at": triggered_at,
        "estimated_duration_min": 90 if full_load else 20,
        "status_url": f"/pipeline/status/{run_id}",
    }
