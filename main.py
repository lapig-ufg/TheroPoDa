# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""Unified CLI and programmatic entrypoint for TheroPoDa v2."""

import argparse
import os
import shutil
import sqlite3
from typing import Optional, Sequence

import pandas as pd
from loguru import logger
from skmap import parallel
from skmap.misc import date_range, ttprint

from mask_resolver import inspect_mask_spec
from theropoda import build_id_list, init_ee, run as theropoda_run
from trend_analysis import run as trend_run


def _resolve_window(collection: str, window: Optional[int]) -> int:
    if window is not None and int(window) > 0:
        return int(window)
    if collection == "Landsat":
        return 16
    return 15


def run_analysis(
    asset: str,
    id_field: str,
    collection: str,
    output_name: str,
    output_folder: str = "",
    start_date: str = "2019-01-01",
    end_date: str = "2025-01-01",
    window: Optional[int] = None,
    n_cores: int = 12,
    project: Optional[str] = None,
    mask: Optional[str] = None,
    mask_classes: Optional[Sequence] = None,
    mask_start_year: Optional[int] = None,
    mask_band: Optional[str] = None,
) -> str:
    """Run the full TheroPoDa extraction, gap-filling, and trend analysis pipeline."""
    if output_folder:
        os.makedirs(output_folder, exist_ok=True)

    init_ee(project)

    mask_spec = inspect_mask_spec(
        mask_input=mask,
        classes=mask_classes,
        mask_start_year=mask_start_year,
        mask_band=mask_band,
    )
    if mask_spec is not None:
        logger.info(
            f"Mask resolved: asset='{mask_spec.asset_id}' | mode='{mask_spec.mode}' | "
            f"classes={mask_spec.classes} | years={mask_spec.min_year}..{mask_spec.max_year}"
        )

    db = asset.split("/")[-1]
    output_prefix = os.path.join(output_folder, output_name)
    db_path = f"{output_prefix}.db"

    with sqlite3.connect(db_path, timeout=60) as con:
        con.execute("PRAGMA journal_mode=WAL;")

    poly_list_path = f"{output_prefix}_polygonList.txt"
    if not os.path.isfile(poly_list_path):
        build_id_list(asset, id_field, output_folder, output_name, project=project)

    theropoda_run(
        asset=asset,
        id_field=id_field,
        output_name=output_name,
        output_folder=output_folder,
        db=db,
        collection=collection,
        n_cores=n_cores,
        mask_spec=mask_spec,
        project=project,
        start_date=start_date,
        end_date=end_date,
    )

    output_file_trends = f"{output_prefix}_trend_analysis.pq"
    final_parquet = f"{output_prefix}_trend_analysis.parquet"

    ttprint(f"Preparing {output_name}")
    with sqlite3.connect(db_path, timeout=60) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        table_name = "observations" if "observations" in tables else "restoration"
        con.execute(f"CREATE INDEX IF NOT EXISTS {table_name}_id_pol ON {table_name} ({id_field})")
        con.commit()
        idx_sql = (
            f"SELECT {id_field}, MIN(date) AS min_date, MAX(date) AS max_date, COUNT(*) AS count "
            f"FROM {table_name} GROUP BY 1 ORDER BY 1"
        )
        idx = pd.read_sql_query(idx_sql, con=con)

    eff_window = _resolve_window(collection, window)
    dt_days = list(date_range(start_date, end_date, date_unit="days", date_step=eff_window, ignore_29feb=True))
    season_size = max(3, round(365 / eff_window))

    job_args = [
        (db_path, r[id_field], dt_days, season_size, id_field, output_file_trends)
        for _, r in idx.iterrows()
    ]

    ttprint(f"Starting trend analysis on {len(job_args)} polygons (window={eff_window}d, season_size={season_size})")
    for _ in parallel.job(trend_run, job_args, joblib_args={"backend": "multiprocessing"}):
        continue

    df2conv = pd.read_parquet(output_file_trends)
    df2conv.to_parquet(final_parquet)
    shutil.rmtree(output_file_trends, ignore_errors=True)
    ttprint(f"Saved final trend analysis to {final_parquet}")
    return final_parquet


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="TheroPoDa v2 - Time Series Extraction from GEE, Gap Filling, and Trend Analysis."
    )
    parser.add_argument(
        "-a",
        "--asset",
        type=str,
        required=True,
        help="Earth Engine Vector Asset path or local vector file (.gpkg, .shp, .geojson, .parquet, .zip)",
    )
    parser.add_argument("-id", "--id_field", type=str, required=True, help="Unique polygon ID field name")
    parser.add_argument(
        "-c", "--collection", type=str, required=True, choices=["Sentinel", "Landsat"], help="Satellite collection"
    )
    parser.add_argument("-o", "--output_name", type=str, required=True, help="Output base filename")
    parser.add_argument("-of", "--output_folder", type=str, default="", help="Output directory (default: current dir)")
    parser.add_argument("-start", "--start_date", type=str, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("-end", "--end_date", type=str, required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("-w", "--window", type=int, default=None, help="Temporal window in days (default: 15 S2 / 16 LS)")
    parser.add_argument("-n", "--n_cores", type=int, default=12, help="Number of parallel workers (default: 12)")
    parser.add_argument("-p", "--project", type=str, default=None, help="Optional Google Earth Engine Cloud project ID")
    parser.add_argument(
        "-m",
        "--mask",
        type=str,
        default=None,
        help="Optional LULC mask asset path or preset ('mapbiomas-pasture', 'mapbiomas-pasture-grasslands')",
    )
    parser.add_argument(
        "-mc",
        "--mask-classes",
        nargs="+",
        default=None,
        help="Class values to keep in the mask (e.g. --mask-classes 15 11 12 or 15,11,12)",
    )
    parser.add_argument(
        "--mask-start-year",
        type=int,
        default=None,
        help="Start year for multiband masks whose band names do not contain years",
    )
    parser.add_argument(
        "--mask-band",
        type=str,
        default=None,
        help="Explicit band name to use as a static mask from a multiband asset",
    )
    return parser


if __name__ == "__main__":
    parsed = build_arg_parser().parse_args()
    run_analysis(
        asset=parsed.asset,
        id_field=parsed.id_field,
        collection=parsed.collection,
        output_name=parsed.output_name,
        output_folder=parsed.output_folder,
        start_date=parsed.start_date,
        end_date=parsed.end_date,
        window=parsed.window,
        n_cores=parsed.n_cores,
        project=parsed.project,
        mask=parsed.mask,
        mask_classes=parsed.mask_classes,
        mask_start_year=parsed.mask_start_year,
        mask_band=parsed.mask_band,
    )
