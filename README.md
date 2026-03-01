# Renewable Project Atlas

Geospatial pipeline + FastAPI microservice + React dashboard for renewable energy siting intelligence.
Portfolio project built to the **Enverus / Pearl Street Technologies** data engineering stack.

## Stack
| Layer | Technology |
|-------|-----------|
| Pipeline | Python 3.11, GeoPandas, GeoAlchemy2, Pandas |
| Cloud | AWS S3, RDS PostgreSQL, ECS Fargate |
| Database | PostgreSQL 15 + PostGIS 3.3 |
| API | FastAPI, Redis cache, Uvicorn |
| Frontend | React 18, TypeScript, Mapbox GL JS, Recharts |
| IaC | Terraform |
| Containers | Docker, Docker Compose |

## Data Sources (all free / public)
| Dataset | Source | URL |
|---------|--------|-----|
| Utility-scale solar projects | LBNL Tracking the Sun | https://emp.lbl.gov/tracking-the-sun |
| Electric substations | HIFLD Open Data | https://hifld-geoplatform.opendata.arcgis.com |
| Transmission lines | HIFLD Open Data | https://hifld-geoplatform.opendata.arcgis.com |
| Power plant registry | EPA eGRID 2022 | https://www.epa.gov/egrid |
| Land cover | NLCD 2021 | https://www.mrlc.gov/data |
| Elevation / slope | USGS 3DEP | https://www.usgs.gov/3d-elevation-program |

## Quick Start (local)

```bash
# 1. Clone and set up environment
git clone https://github.com/yourname/renewable-atlas
cd renewable-atlas
cp .env.example .env          # fill in your values

# 2. Spin up Postgres + PostGIS + Redis
docker compose up -d

# 3. Install Python deps and run pipeline
pip install -r requirements.txt
python pipeline/ingest.py     # downloads + loads all datasets
python pipeline/score.py      # computes siting scores

# 4. Start FastAPI
uvicorn api.main:app --reload --port 8000

# 5. Start React frontend
cd frontend
npm install
npm run dev                   # runs on http://localhost:5173
```

## Project Structure

```
renewable-atlas/
├── pipeline/
│   ├── ingest.py          # GeoPandas ETL → PostGIS
│   ├── score.py           # Siting score engine
│   ├── schema.sql         # PostGIS schema + indexes
│   └── config.py          # Settings (reads from .env)
├── api/
│   ├── main.py            # FastAPI app + all routes
│   ├── database.py        # SQLAlchemy engine + session
│   └── models.py          # Pydantic response models
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── MapView.tsx
│   │   │   ├── ScoreCard.tsx
│   │   │   ├── FilterPanel.tsx
│   │   │   └── ProjectTable.tsx
│   │   ├── hooks/
│   │   │   ├── useProjects.ts
│   │   │   └── useProjectScore.ts
│   │   └── state/
│   │       └── atoms.ts
│   ├── package.json
│   └── vite.config.ts
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── docker/
│   └── Dockerfile.api
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects` | Spatial bbox query → GeoJSON |
| GET | `/projects/{id}/score` | Full 6-dimension siting scorecard |
| GET | `/clusters` | Server-side K-means clusters for map |
| GET | `/substations/nearest` | Nearest substation to a point |
| POST | `/pipeline/trigger` | Kick off Airflow ingestion DAG |

## Siting Score Dimensions

| Dimension | Weight | Logic |
|-----------|--------|-------|
| Substation distance | 30% | 100pts at 0km → 0 at 25km (linear) |
| Transmission voltage | 25% | 345kV=100, 230kV=70, 115kV=40 |
| Queue competition | 15% | Inverse sigmoid on projects/km² within 50km |
| Land use (NLCD) | 15% | Ag/barren=90, shrub=70, developed=20 |
| Slope (USGS DEM) | 15% | Solar: <3°=100. Wind: 5–15°=90 |
| Exclusion zones | hard | Wetlands/protected/flood = 0 (disqualifier) |

## Key Engineering Decisions

**PostGIS GIST index** — bbox + distance queries in <50ms at 290K records vs full table scan.

**BRIN on install_date** — minimal storage overhead for an append-only time column vs B-tree.

**Partial index on project_scores WHERE excluded=FALSE** — fast leaderboard queries skip disqualified sites.

**Redis cache** — bbox GeoJSON cached 5 min, scorecards 1 hr. Prevents repeated expensive spatial joins.

**GeoAlchemy2** — typed PostGIS geometry inserts from GeoPandas. No hand-rolled WKT strings in pipeline.

**Terraform modules** — rds / ecs / s3 are independently deployable so you can tear down ECS without touching the DB.
