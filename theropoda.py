# -*- coding: utf-8 -*-
"""TheroPoDa core extraction module for Google Earth Engine NDVI time series."""

import os
import sqlite3
import time
from typing import Optional

import ee
import pandas as pd
from joblib import Parallel, delayed
from loguru import logger

from mask_resolver import MaskSpec, build_ee_mask

logger.add("log_do_.log", rotation="500 MB")

TABLE_NAME = "observations"
_EE_INITIALIZED = False


def init_ee(project: Optional[str] = None) -> None:
    """Initialize Earth Engine lazily using the high-volume endpoint."""
    global _EE_INITIALIZED
    if _EE_INITIALIZED:
        return
    kwargs = {"opt_url": "https://earthengine-highvolume.googleapis.com"}
    if project:
        kwargs["project"] = project
    ee.Initialize(**kwargs)
    _EE_INITIALIZED = True


def _parse_poly_id(raw_id):
    """Preserve integer IDs when numeric, otherwise keep as string."""
    text = str(raw_id).strip()
    try:
        return int(text)
    except ValueError:
        return text


def getTimeSeries(
    geometry: ee.Feature,
    collection: str,
    id_field: str,
    bestEffort: bool = False,
    mask_spec: Optional[MaskSpec] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Retrieve NDVI time series data from Sentinel-2 or Landsat 8/9 for a geometry."""

    def maskEdges(img):
        return img.updateMask(img.select("B8A").mask().updateMask(img.select("B9").mask()))

    def mask_and_ndvi_ls(img):
        sat_name = ee.String(img.get("SPACECRAFT_ID"))
        mask_exp = "(b('QA_PIXEL') == 21824 || b('QA_PIXEL') == 21952)"
        cloud_mask = img.expression(mask_exp).add(img.gt(0)).select([0], ["QA"])
        red_nir = img.select(["SR_B5", "SR_B4"], ["RED", "NIR"]).multiply(0.0000275).add(-0.2)
        ndvi = red_nir.updateMask(cloud_mask).normalizedDifference(["RED", "NIR"]).select([0], ["NDVI"])
        return img.addBands([ndvi, ee.Image.constant(1).rename(["full"])], None, True).set(
            {"system:time_start": img.get("system:time_start"), "satelite": sat_name}
        )

    def mask_and_ndvi_s2(img):
        sat_name = ee.String(img.get("SPACECRAFT_NAME"))
        mask = img.select("cs").gte(0.5)
        bad_values_filter = img.select("B8").gte(0)
        ndvi = img.updateMask(mask.multiply(bad_values_filter)).normalizedDifference(["B8", "B4"]).select([0], ["NDVI"])
        return img.addBands([ndvi, ee.Image.constant(1).rename(["full"])], None, True).set(
            {"system:time_start": img.get("system:time_start"), "satelite": sat_name}
        )

    def select_collection(col_name: str):
        geom = ee.Feature(geometry).geometry()
        if col_name == "Landsat":
            l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
            l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
            col = l8.merge(l9).filterBounds(geom)
            if start_date and end_date:
                col = col.filterDate(start_date, end_date)
            return col.map(mask_and_ndvi_ls)
        if col_name == "Sentinel":
            s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(geom)
            cs_plus = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED").filterBounds(geom)
            if start_date and end_date:
                s2 = s2.filterDate(start_date, end_date)
                cs_plus = cs_plus.filterDate(start_date, end_date)
            cs_plus_bands = cs_plus.first().bandNames()
            return s2.linkCollection(cs_plus, cs_plus_bands).map(maskEdges).map(mask_and_ndvi_s2)
        raise ValueError(f"Unsupported collection '{col_name}'. Expected 'Sentinel' or 'Landsat'.")

    def reduceData(img):
        img = ee.Image(img)
        img_date = ee.Date(ee.Number(img.get("system:time_start")))
        img_year = ee.Number(img_date.get("year")).toInt()
        org_date = (
            ee.String(img_year.format())
            .cat("-")
            .cat(ee.String(ee.Number(img_date.get("month")).toInt().format()))
            .cat("-")
            .cat(ee.String(ee.Number(img_date.get("day")).toInt().format()))
        )

        reducers = ee.Reducer.median().combine(reducer2=ee.Reducer.count(), sharedInputs=True)
        geom = ee.Feature(geometry).geometry()
        lulc_mask = build_ee_mask(mask_spec, img_year, geom)
        target_img = img.updateMask(lulc_mask) if lulc_mask is not None else img

        if collection == "Landsat":
            pixel_size = 30
            series = target_img.reduceRegion(reducers, geom, pixel_size, None, None, False, 1e13, 16)
            return (
                ee.Feature(None)
                .set(id_field, ee.Feature(geometry).get(id_field))
                .set("id", ee.String(img.id()))
                .set("date", org_date)
                .set("satelite", img.get("satelite"))
                .set("WRS_PATH", img.get("WRS_PATH"))
                .set("WRS_ROW", img.get("WRS_ROW"))
                .set("AREA_HA", ee.Feature(geometry).area(1).divide(10000))
                .set("NDVI_median", ee.Number(ee.Dictionary(series).get("NDVI_median")))
                .set("Pixel_Count", ee.Number(ee.Dictionary(series).get("NDVI_count")))
                .set("Total_Pixels", ee.Number(ee.Dictionary(series).get("full_count")))
                .set("Pixel_Size", pixel_size)
            )

        pixel_size = 30 if bestEffort else 10
        series = target_img.reduceRegion(reducers, geom, pixel_size, None, None, False, 1e13, 16)
        return (
            ee.Feature(None)
            .set(id_field, ee.Feature(geometry).get(id_field))
            .set("id", ee.String(img.id()))
            .set("date", org_date)
            .set("satelite", img.get("satelite"))
            .set("MGRS_TILE", img.get("MGRS_TILE"))
            .set("AREA_HA", ee.Feature(geometry).area(1).divide(10000))
            .set("NDVI_median", ee.Number(ee.Dictionary(series).get("NDVI_median")))
            .set("Pixel_Count", ee.Number(ee.Dictionary(series).get("NDVI_count")))
            .set("Total_Pixels", ee.Number(ee.Dictionary(series).get("full_count")))
            .set("Pixel_Size", pixel_size)
        )

    img_col = select_collection(collection)
    return ee.FeatureCollection(img_col.map(reduceData)).filter(ee.Filter.notNull(["NDVI_median"]))


def build_time_series(
    index: int,
    obj,
    id_field: str,
    outfile: str,
    asset: str,
    collection: str,
    bestEffort: bool = False,
    mask_spec: Optional[MaskSpec] = None,
    project: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Extract and write NDVI time series to SQLite for a single polygon."""
    init_ee(project)
    samples = ee.FeatureCollection(asset).select(id_field)
    start_time_obj = time.time()
    selected_sample = samples.filter(ee.Filter.eq(id_field, obj)).first()
    fc_info = getTimeSeries(
        ee.Feature(selected_sample),
        collection,
        id_field=id_field,
        bestEffort=bestEffort,
        mask_spec=mask_spec,
        start_date=start_date,
        end_date=end_date,
    ).getInfo()
    point_series = [feat["properties"] for feat in fc_info.get("features", [])]

    if not point_series:
        return "empty", None

    df = pd.DataFrame(point_series)
    df["AREA_HA"] = df["AREA_HA"].round(decimals=4)
    df["NDVI_median"] = df["NDVI_median"].round(decimals=4)
    df["date"] = pd.to_datetime(df["date"])

    with sqlite3.connect(outfile, timeout=60) as conn:
        df.to_sql(TABLE_NAME, conn, if_exists="append", index=False)

    time_spent = round(time.time() - start_time_obj, 3)
    logger.success(f"Index {index} - Object [{obj}] processed in {time_spent} seconds")

    if float(df["AREA_HA"].iloc[0]) < 0.01:
        return None, None
    return True, time_spent


def build_time_series_check(
    index: int,
    obj,
    id_field: str,
    outfile: str,
    asset: str,
    collection: str,
    checker: bool = False,
    mask_spec: Optional[MaskSpec] = None,
    project: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Check if polygon was already processed and run extraction with bestEffort fallback."""
    init_ee(project)
    obj = _parse_poly_id(obj)
    db_file = outfile + ".db"

    if checker:
        with sqlite3.connect(db_file, timeout=60) as conn:
            try:
                df_check_list = pd.read_sql_query(f"SELECT DISTINCT {id_field} FROM {TABLE_NAME}", conn)[id_field].tolist()
            except Exception:
                df_check_list = []
        if obj in df_check_list:
            logger.info(f"Object [{obj}] already in database. Skipping...")
            return {"errors": None, "empty": None, "time": 0}

    errors = None
    empty = None
    elapsed = None

    try:
        status, elapsed = build_time_series(
            index,
            obj,
            id_field,
            db_file,
            asset,
            collection,
            bestEffort=False,
            mask_spec=mask_spec,
            project=project,
            start_date=start_date,
            end_date=end_date,
        )
        if status == "empty":
            logger.warning(f"Index {index} - Object [{obj}] has no valid pixels after mask/date filter. Skipping.")
            return {"errors": None, "empty": obj, "time": None}
        if status is None:
            return {"errors": "ignore", "empty": None, "time": "ignore"}
    except Exception:
        try:
            logger.exception(f"Index {index} - Request [{obj}] failed. Trying bestEffort=True!")
            status, elapsed = build_time_series(
                index,
                obj,
                id_field,
                db_file,
                asset,
                collection,
                bestEffort=True,
                mask_spec=mask_spec,
                project=project,
                start_date=start_date,
                end_date=end_date,
            )
            if status == "empty":
                logger.warning(f"Index {index} - Object [{obj}] empty even with bestEffort. Skipping.")
                return {"errors": None, "empty": obj, "time": None}
            if status is None:
                return {"errors": "ignore", "empty": None, "time": "ignore"}
        except Exception:
            logger.error(f"Index {index} - Request [{obj}] failed permanently. Sending to error list.")
            errors = obj

    return {"errors": errors, "empty": empty, "time": elapsed}


def build_id_list(asset: str, id_field: str, output_folder: str, outname: str, project: Optional[str] = None) -> None:
    """Export sorted polygon IDs from an Earth Engine FeatureCollection to a text file."""
    init_ee(project)
    samples = ee.FeatureCollection(asset).select(id_field)
    sample_size = int(samples.size().getInfo())
    samples_list = samples.toList(50000 if sample_size < 50000 else sample_size)
    filename = os.path.join(output_folder, f"{outname}_polygonList.txt")

    ids = samples_list.map(lambda feat: ee.Feature(feat).get(id_field)).sort().getInfo()
    with open(filename, "w", encoding="utf-8") as polygon_file:
        for polygon in ids:
            polygon_file.write(f"{polygon}\n")


def run(
    asset: str,
    id_field: str,
    output_name: str,
    output_folder: str,
    db: str,
    collection: str,
    n_cores: int = 12,
    mask_spec: Optional[MaskSpec] = None,
    project: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> None:
    """Coordinate parallel GEE NDVI extraction across all polygon IDs."""
    init_ee(project)
    output_prefix = os.path.join(output_folder, output_name)
    start_time = time.time()
    poly_list_path = f"{output_prefix}_polygonList.txt"

    with open(poly_list_path, "r", encoding="utf-8") as f:
        list_polygons = [_parse_poly_id(line) for line in f if line.strip()]

    total = len(list_polygons)
    db_file = f"{output_prefix}.db"
    already_done = set()
    if os.path.exists(db_file):
        with sqlite3.connect(db_file, timeout=60) as conn:
            for tbl in (TABLE_NAME, "restoration"):
                try:
                    existing = pd.read_sql_query(f"SELECT DISTINCT {id_field} FROM {tbl}", conn)[id_field].tolist()
                    already_done.update(existing)
                    break
                except Exception:
                    continue

    remaining_polygons = [obj for obj in list_polygons if obj not in already_done]
    logger.info(
        f"Number of objects to process: {len(remaining_polygons)} "
        f"(total={total}, already in DB={len(already_done)})"
    )
    if len(remaining_polygons) > 1000:
        logger.info("Go take a coffee and watch a series... it will take a while!")

    worker_args = [
        (idx, obj, id_field, output_prefix, asset, collection, False, mask_spec, project, start_date, end_date)
        for idx, obj in enumerate(remaining_polygons)
    ]

    infos = Parallel(n_jobs=int(n_cores), backend="multiprocessing")(
        delayed(build_time_series_check)(*args) for args in worker_args
    )

    time_list = [0] + [item["time"] for item in infos if item["time"] not in (None, "ignore")]
    errors_list = [item["errors"] for item in infos if item["errors"] not in (None, "ignore")]
    empty_list = [item["empty"] for item in infos if item.get("empty") is not None]

    errors_path = f"{output_prefix}_errors_polygon.txt"
    with open(errors_path, "w", encoding="utf-8") as errors_file:
        for polygon in errors_list:
            errors_file.write(f"{polygon}\n")

    empty_path = f"{output_prefix}_empty_polygon.txt"
    with open(empty_path, "w", encoding="utf-8") as empty_file:
        for polygon in empty_list:
            empty_file.write(f"{polygon}\n")

    avg_time = round(pd.Series(time_list, dtype=float).mean(), 2)
    logger.success(f"The average processing time was {avg_time} seconds")
    logger.info(f"Empty polygons after mask/date filter: {len(empty_list)} | Failed polygons: {len(errors_list)}")
    logger.success(f"Processing finished. All the work took {round(time.time() - start_time, 3)} seconds to complete")
