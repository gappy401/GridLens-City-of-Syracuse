"""api/models.py — Pydantic response models."""

from typing import Any, Optional
from pydantic import BaseModel


class ProjectProperties(BaseModel):
    id: int
    name: Optional[str]
    fuel_type: Optional[str]
    capacity_mw: Optional[float]
    state: Optional[str]
    score: Optional[float]


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: dict[str, Any]
    properties: ProjectProperties


class GeoJSONCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[GeoJSONFeature]
    total: int


class SubstationInfo(BaseModel):
    id: int
    name: Optional[str]
    voltage_kv: Optional[float]
    owner: Optional[str]
    dist_km: Optional[float]


class ScoreBreakdown(BaseModel):
    total: float
    substation: float
    voltage: float
    competition: float
    land_use: float
    slope: float
    excluded: bool


class ProjectScoreResponse(BaseModel):
    project: ProjectProperties
    nearest_substation: Optional[SubstationInfo]
    scores: ScoreBreakdown


class ClusterProperties(BaseModel):
    cluster_id: int
    project_count: int
    total_mw: Optional[float]
    avg_score: Optional[float]


class NearestSubstationResponse(BaseModel):
    substation: SubstationInfo
    geometry: dict[str, Any]


class PipelineTriggerResponse(BaseModel):
    dag_run_id: str
    status: str
    triggered_at: str
    estimated_duration_min: int
    status_url: str
