"""
pipeline/ingest.py
------------------
ETL pipeline for the Renewable Project Atlas.

Steps:
  1. Download raw datasets from S3 (or fall back to local paths for dev)
  2. Load + reproject each dataset to EPSG:4326
  3. Load into PostGIS via GeoAlchemy2
  4. Enrich projects with nearest substation (PostGIS KNN query)

Data sources:
  - LBNL Tracking the Sun (utility-scale solar CSV)
  - HIFLD Electric Substations (shapefile zip)
  - HIFLD Transmission Lines (shapefile zip)
  - EPA eGRID 2022 plant CSV

Usage:
  python pipeline/ingest.py
  python pipeline/ingest.py --local   # skip S3, use ./data/ directory
"""

import argparse
import logging
import sys
from pathlib import Path

import boto3
import geopandas as gpd
import pandas as pd
from geoalchemy2 import Geometry, WKTElement
from sqlalchemy import create_engine, text

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Column rename maps ────────────────────────────────────────────────────────

LBNL_COLS = {
    "latitude": "lat",
    "longitude": "lon",
    "system_capacity_dc": "capacity_mw",
    "installation_date": "install_date",
    "technology": "fuel_type",
    "state": "state",
    "county": "county",
    "project_name": "name",
}

EGRID_COLS = {
    "LAT": "lat",
    "LON": "lon",
    "NAMEPCAP": "capacity_mw",
    "PLFUELCT": "fuel_type",
    "PSTATABB": "state",
    "CNTYNAME": "county",
    "PNAME": "name",
}

HIFLD_SUB_COLS = {
    "NAME": "name",
    "VOLTAGE": "voltage_kv",
    "OWNER": "owner",
    "STATE": "state",
}

HIFLD_LINE_COLS = {
    "VOLTAGE": "voltage_kv",
    "OWNER": "owner",
    "STATE": "state",
}


# ── S3 helpers ────────────────────────────────────────────────────────────────

def download_from_s3(local_dir: Path) -> dict[str, Path]:
    """Download all raw source files from S3 to a local temp directory."""
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    sources = {
        "lbnl_solar":    "raw/lbnl_tracking_the_sun.csv",
        "hifld_subs":    "raw/Electric_Substations.zip",
        "hifld_lines":   "raw/Transmission_Lines.zip",
        "egrid_plants":  "raw/egrid2022_plant.csv",
    }
    paths = {}
    local_dir.mkdir(parents=True, exist_ok=True)
    for key, s3_key in sources.items():
        dest = local_dir / Path(s3_key).name
        if not dest.exists():
            log.info("Downloading s3://%s/%s → %s", settings.S3_BUCKET, s3_key, dest)
            s3.download_file(settings.S3_BUCKET, s3_key, str(dest))
        else:
            log.info("Using cached %s", dest)
        paths[key] = dest
    return paths


def use_local_data(local_dir: Path) -> dict[str, Path]:
    """For local dev: point directly at files in ./data/"""
    return {
        "lbnl_solar":   local_dir / "lbnl_tracking_the_sun.csv",
        "hifld_subs":   local_dir / "Electric_Substations.zip",
        "hifld_lines":  local_dir / "Transmission_Lines.zip",
        "egrid_plants": local_dir / "egrid2022_plant.csv",
    }


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_lbnl_solar(csv_path: Path) -> gpd.GeoDataFrame:
    log.info("Loading LBNL Tracking the Sun from %s", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)
    df = df.rename(columns={k: v for k, v in LBNL_COLS.items() if k in df.columns})
    df = df.dropna(subset=["lat", "lon"])
    df["capacity_mw"] = pd.to_numeric(df.get("capacity_mw"), errors="coerce")
    df["install_date"] = pd.to_datetime(df.get("install_date"), errors="coerce")
    df["fuel_type"] = df.get("fuel_type", "Solar").fillna("Solar")
    df["source"] = "lbnl"
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )
    keep = ["name", "fuel_type", "capacity_mw", "state", "county", "install_date", "source", "geometry"]
    return gdf[[c for c in keep if c in gdf.columns]]


def load_egrid_plants(csv_path: Path) -> gpd.GeoDataFrame:
    log.info("Loading EPA eGRID from %s", csv_path)
    df = pd.read_excel(csv_path, sheet_name="PLNT22", header=1) if str(csv_path).endswith(".xlsx") \
        else pd.read_csv(csv_path, low_memory=False)
    df = df.rename(columns={k: v for k, v in EGRID_COLS.items() if k in df.columns})
    df = df.dropna(subset=["lat", "lon"])
    # Keep only renewables
    df = df[df["fuel_type"].isin(["SOLAR", "WIND", "BIOMASS", "GEOTHM", "HYDRO"])]
    df["capacity_mw"] = pd.to_numeric(df.get("capacity_mw"), errors="coerce")
    df["fuel_type"] = df["fuel_type"].str.title()
    df["source"] = "egrid"
    df["install_date"] = None
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )
    keep = ["name", "fuel_type", "capacity_mw", "state", "county", "install_date", "source", "geometry"]
    return gdf[[c for c in keep if c in gdf.columns]]


def load_substations(shp_zip: Path) -> gpd.GeoDataFrame:
    log.info("Loading HIFLD substations from %s", shp_zip)
    gdf = gpd.read_file(f"zip://{shp_zip}")
    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf.rename(columns={k: v for k, v in HIFLD_SUB_COLS.items() if k in gdf.columns})
    gdf["voltage_kv"] = pd.to_numeric(gdf.get("voltage_kv"), errors="coerce")
    keep = ["name", "voltage_kv", "owner", "state", "geometry"]
    return gdf[[c for c in keep if c in gdf.columns]]


def load_transmission_lines(shp_zip: Path) -> gpd.GeoDataFrame:
    log.info("Loading HIFLD transmission lines from %s", shp_zip)
    gdf = gpd.read_file(f"zip://{shp_zip}")
    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf.rename(columns={k: v for k, v in HIFLD_LINE_COLS.items() if k in gdf.columns})
    gdf["voltage_kv"] = pd.to_numeric(gdf.get("voltage_kv"), errors="coerce")
    # Only keep high-voltage lines (≥69 kV)
    gdf = gdf[gdf["voltage_kv"] >= 69]
    keep = ["voltage_kv", "owner", "state", "geometry"]
    return gdf[[c for c in keep if c in gdf.columns]]


# ── PostGIS loaders ───────────────────────────────────────────────────────────

def gdf_to_postgis(
    gdf: gpd.GeoDataFrame,
    table: str,
    engine,
    geom_type: str = "POINT",
    if_exists: str = "replace",
) -> int:
    """
    Load a GeoDataFrame into PostGIS using GeoAlchemy2 typed columns.
    Returns number of rows inserted.
    """
    df = gdf.copy()
    df["geom"] = df["geometry"].apply(
        lambda g: WKTElement(g.wkt, srid=4326) if g is not None else None
    )
    df = df.drop(columns=["geometry"])
    df = df.dropna(subset=["geom"])

    df.to_sql(
        table,
        engine,
        if_exists=if_exists,
        index=False,
        dtype={"geom": Geometry(geom_type, srid=4326)},
        chunksize=5000,
        method="multi",
    )

    # Recreate GIST index (dropped on replace)
    with engine.connect() as conn:
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_{table}_geom
            ON {table} USING GIST (geom)
        """))
        conn.commit()

    log.info("Loaded %d rows → %s (GIST indexed)", len(df), table)
    return len(df)


# ── Spatial enrichment ────────────────────────────────────────────────────────

ENRICH_SQL = text("""
UPDATE projects p
SET
    nearest_substation_id = nearest.sub_id,
    substation_dist_km    = nearest.dist_km
FROM (
    SELECT DISTINCT ON (p2.id)
        p2.id AS proj_id,
        s.id  AS sub_id,
        ST_Distance(p2.geom::geography, s.geom::geography) / 1000.0 AS dist_km
    FROM projects p2
    CROSS JOIN LATERAL (
        SELECT id, geom
        FROM substations
        ORDER BY substations.geom <-> p2.geom
        LIMIT 1
    ) s
) nearest
WHERE p.id = nearest.proj_id
""")


def enrich_nearest_substation(engine) -> None:
    log.info("Enriching projects with nearest substation (KNN lateral join)...")
    with engine.connect() as conn:
        result = conn.execute(ENRICH_SQL)
        conn.commit()
    log.info("Enriched %d projects", result.rowcount)


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Renewable Atlas ingest pipeline")
    parser.add_argument("--local", action="store_true", help="Use ./data/ instead of S3")
    args = parser.parse_args()

    tmp = Path("/tmp/atlas-raw")
    paths = use_local_data(Path("data")) if args.local else download_from_s3(tmp)

    engine = create_engine(settings.DATABASE_URL, echo=False)

    # Load in dependency order: substations first (projects FK references them)
    if paths["hifld_subs"].exists():
        subs_gdf = load_substations(paths["hifld_subs"])
        gdf_to_postgis(subs_gdf, "substations", engine, geom_type="POINT")
    else:
        log.warning("Substations file not found, skipping: %s", paths["hifld_subs"])

    if paths["hifld_lines"].exists():
        lines_gdf = load_transmission_lines(paths["hifld_lines"])
        gdf_to_postgis(lines_gdf, "transmission_lines", engine, geom_type="LINESTRING")
    else:
        log.warning("Transmission lines file not found, skipping")

    # Merge LBNL + eGRID into a single projects table
    frames = []
    if paths["lbnl_solar"].exists():
        frames.append(load_lbnl_solar(paths["lbnl_solar"]))
    if paths["egrid_plants"].exists():
        frames.append(load_egrid_plants(paths["egrid_plants"]))

    if not frames:
        log.error("No project data found. Download source files to ./data/ first.")
        sys.exit(1)

    projects_gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    log.info("Total project records: %d", len(projects_gdf))
    gdf_to_postgis(projects_gdf, "projects", engine, geom_type="POINT")

    # Spatial enrichment
    enrich_nearest_substation(engine)

    log.info("✓ Ingest complete. Run pipeline/score.py next.")


if __name__ == "__main__":
    main()
