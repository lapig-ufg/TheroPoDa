"""Dynamic LULC mask resolution and year-band mapping for Google Earth Engine."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Optional, Sequence
import ee

YEAR_PATTERN = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")

MASK_PRESETS = {
    "mapbiomas-pasture": {
        "asset": "projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3",
        "classes": [15],
        "description": "MapBiomas Brazil Collection 11 - Pasture (class 15)",
    },
    "mapbiomas-pasture-grasslands": {
        "asset": "projects/mapbiomas-public/assets/brazil/lulc/collection10/mapbiomas_brazil_collection10_coverage_v2",
        "classes": [15],
        "grassland_classes": [11, 12],
        "description": "MapBiomas Brazil Collection 10 - Pasture (15) + Grasslands in SC/RS/Pantanal (11, 12)",
    },
}


@dataclass(frozen=True)
class MaskSpec:
    """Resolved specification for an Earth Engine LULC mask."""

    asset_id: str
    mode: str  # 'multiband_years' | 'image_collection' | 'static_image' | 'grasslands_preset'
    classes: Optional[List[int]] = None
    year_to_band: Optional[Dict[int, str]] = None
    available_years: Optional[List[int]] = None
    static_band: Optional[str] = None
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    preset_name: Optional[str] = None


def parse_classes_arg(raw_classes: Optional[Sequence]) -> Optional[List[int]]:
    """Parse class IDs from CLI/GUI inputs (e.g., ['15', '11,12'] -> [15, 11, 12])."""
    if not raw_classes:
        return None
    if isinstance(raw_classes, str):
        raw_classes = [raw_classes]
    parsed: List[int] = []
    for item in raw_classes:
        for token in str(item).replace(";", ",").split(","):
            token = token.strip()
            if token:
                parsed.append(int(token))
    return parsed or None


def parse_year_bands(
    band_names: Sequence[str],
    mask_start_year: Optional[int] = None,
    mask_band: Optional[str] = None,
) -> Dict[str, object]:
    """Infer year-to-band mapping or static band mode from an image's band names.

    Pure helper so it can be unit-tested without an Earth Engine session.
    """
    bands = list(band_names)
    if not bands:
        raise ValueError("Mask image has no bands.")

    if mask_band:
        if mask_band not in bands:
            raise ValueError(f"Requested mask band '{mask_band}' not found in {bands}.")
        return {"mode": "static_image", "static_band": mask_band, "year_to_band": None}

    year_to_band: Dict[int, str] = {}
    for band in bands:
        match = YEAR_PATTERN.search(band)
        if match:
            year_to_band[int(match.group(1))] = band

    if len(year_to_band) >= 1 and (len(year_to_band) == len(bands) or len(bands) > 1):
        sorted_years = sorted(year_to_band)
        return {
            "mode": "multiband_years",
            "year_to_band": {y: year_to_band[y] for y in sorted_years},
            "min_year": sorted_years[0],
            "max_year": sorted_years[-1],
            "static_band": None,
        }

    if len(bands) == 1:
        return {"mode": "static_image", "static_band": bands[0], "year_to_band": None}

    if mask_start_year is not None:
        mapped = {mask_start_year + idx: band for idx, band in enumerate(bands)}
        return {
            "mode": "multiband_years",
            "year_to_band": mapped,
            "min_year": mask_start_year,
            "max_year": mask_start_year + len(bands) - 1,
            "static_band": None,
        }

    raise ValueError(
        f"Could not infer years from multiband mask {bands[:5]}... "
        "Pass --mask-start-year or --mask-band to disambiguate."
    )


def inspect_mask_spec(
    mask_input: Optional[str],
    classes: Optional[Sequence] = None,
    mask_start_year: Optional[int] = None,
    mask_band: Optional[str] = None,
) -> Optional[MaskSpec]:
    """Inspect a GEE mask asset (or preset name) once at startup and return a MaskSpec."""
    if not mask_input:
        return None

    parsed_classes = parse_classes_arg(classes)

    if mask_input == "mapbiomas-pasture-grasslands":
        preset = MASK_PRESETS[mask_input]
        band_names = ee.Image(preset["asset"]).bandNames().getInfo()
        parsed = parse_year_bands(band_names)
        return MaskSpec(
            asset_id=preset["asset"],
            mode="grasslands_preset",
            classes=parsed_classes or preset["classes"],
            year_to_band=parsed["year_to_band"],
            min_year=parsed["min_year"],
            max_year=parsed["max_year"],
            preset_name=mask_input,
        )

    if mask_input in MASK_PRESETS:
        preset = MASK_PRESETS[mask_input]
        asset_id = preset["asset"]
        effective_classes = parsed_classes or preset["classes"]
        preset_name = mask_input
    else:
        asset_id = mask_input
        effective_classes = parsed_classes
        preset_name = None

    asset_info = ee.data.getAsset(asset_id)
    asset_type = asset_info.get("type", "IMAGE")

    if asset_type == "IMAGE_COLLECTION":
        col = ee.ImageCollection(asset_id)
        timestamps = col.aggregate_array("system:time_start").getInfo()
        years = sorted(
            {
                int(ee.Date(ts).get("year").getInfo())
                for ts in timestamps
                if ts is not None
            }
        )
        if not years:
            prop_years = col.aggregate_array("year").getInfo()
            years = sorted({int(y) for y in prop_years if y is not None})
        if not years:
            raise ValueError(f"ImageCollection '{asset_id}' has no 'system:time_start' or 'year' metadata.")
        return MaskSpec(
            asset_id=asset_id,
            mode="image_collection",
            classes=effective_classes,
            available_years=years,
            static_band=mask_band,
            min_year=years[0],
            max_year=years[-1],
            preset_name=preset_name,
        )

    band_names = ee.Image(asset_id).bandNames().getInfo()
    parsed = parse_year_bands(band_names, mask_start_year=mask_start_year, mask_band=mask_band)
    return MaskSpec(
        asset_id=asset_id,
        mode=parsed["mode"],
        classes=effective_classes,
        year_to_band=parsed["year_to_band"],
        static_band=parsed["static_band"],
        min_year=parsed.get("min_year"),
        max_year=parsed.get("max_year"),
        preset_name=preset_name,
    )


def _apply_class_filter(image: ee.Image, classes: Optional[List[int]]) -> ee.Image:
    """Convert an Earth Engine LULC image into a boolean (0/1) mask for target classes."""
    if not classes:
        return image.gt(0)
    if len(classes) == 1:
        return image.eq(classes[0])
    return image.remap(classes, [1] * len(classes), 0).gt(0)


def build_ee_mask(spec: Optional[MaskSpec], img_year: ee.Number, geometry: ee.Geometry) -> Optional[ee.Image]:
    """Build the server-side Earth Engine boolean mask for a given image year and geometry."""
    if spec is None:
        return None

    if spec.mode == "static_image":
        base = ee.Image(spec.asset_id)
        if spec.static_band:
            base = base.select(spec.static_band)
        return _apply_class_filter(base, spec.classes).clip(geometry)

    clamped_year = ee.Number(img_year).max(spec.min_year).min(spec.max_year).toInt()

    if spec.mode == "multiband_years":
        ee_band_map = ee.Dictionary({str(y): b for y, b in spec.year_to_band.items()})
        band_name = ee.String(ee_band_map.get(clamped_year.format()))
        base = ee.Image(spec.asset_id).select(band_name)
        return _apply_class_filter(base, spec.classes).clip(geometry)

    if spec.mode == "image_collection":
        col = ee.ImageCollection(spec.asset_id).filter(
            ee.Filter.calendarRange(clamped_year, clamped_year, "year")
        )
        base = col.mosaic()
        if spec.static_band:
            base = base.select(spec.static_band)
        return _apply_class_filter(base, spec.classes).clip(geometry)

    if spec.mode == "grasslands_preset":
        ee_band_map = ee.Dictionary({str(y): b for y, b in spec.year_to_band.items()})
        band_name = ee.String(ee_band_map.get(clamped_year.format()))
        mapbiomas = ee.Image(spec.asset_id).select(band_name).clip(geometry)

        states = (
            ee.FeatureCollection("projects/ee-vieiramesquita/assets/BR_UF_2022")
            .filter(ee.Filter.inList("SIGLA_UF", ["SC", "RS"]))
            .map(lambda feat: feat.set("cd_id", 1))
            .reduceToImage(properties=["cd_id"], reducer=ee.Reducer.max())
            .gt(0)
        )
        pantanal = (
            ee.FeatureCollection("users/vieiramesquita/lm_bioma_250")
            .filter(ee.Filter.eq("Bioma", "Pantanal"))
            .reduceToImage(properties=["CD_Bioma"], reducer=ee.Reducer.max())
            .gt(0)
        )
        grassland_region = ee.ImageCollection([states, pantanal]).mosaic()
        primary_mask = _apply_class_filter(mapbiomas, spec.classes)
        grassland_mask = mapbiomas.updateMask(grassland_region).remap([11, 12], [1, 1], 0)
        return primary_mask.add(grassland_mask.unmask()).gt(0)

    raise ValueError(f"Unsupported mask mode: {spec.mode}")
