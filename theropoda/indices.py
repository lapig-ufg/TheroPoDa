"""Spectral index presets and scaled reflectance helpers for Sentinel-2 and Landsat 8/9."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence
import ee

INDEX_PRESETS: Dict[str, Dict[str, object]] = {
    "NDVI": {
        "name": "Normalized Difference Vegetation Index",
        "formula": "(NIR - RED) / (NIR + RED)",
        "collections": ("Sentinel", "Landsat"),
    },
    "EVI": {
        "name": "Enhanced Vegetation Index",
        "formula": "2.5 * (NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1)",
        "collections": ("Sentinel", "Landsat"),
    },
    "SAVI": {
        "name": "Soil-Adjusted Vegetation Index",
        "formula": "1.5 * (NIR - RED) / (NIR + RED + 0.5)",
        "collections": ("Sentinel", "Landsat"),
    },
    "NDMI": {
        "name": "Normalized Difference Moisture Index",
        "formula": "(NIR - SWIR1) / (NIR + SWIR1)",
        "collections": ("Sentinel", "Landsat"),
    },
    "NDWI": {
        "name": "Normalized Difference Water Index (McFeeters)",
        "formula": "(GREEN - NIR) / (GREEN + NIR)",
        "collections": ("Sentinel", "Landsat"),
    },
    "NBR": {
        "name": "Normalized Burn Ratio",
        "formula": "(NIR - SWIR2) / (NIR + SWIR2)",
        "collections": ("Sentinel", "Landsat"),
    },
    "BSI": {
        "name": "Bare Soil Index",
        "formula": "((SWIR1 + RED) - (NIR + BLUE)) / ((SWIR1 + RED) + (NIR + BLUE))",
        "collections": ("Sentinel", "Landsat"),
    },
    "GNDVI": {
        "name": "Green Normalized Difference Vegetation Index",
        "formula": "(NIR - GREEN) / (NIR + GREEN)",
        "collections": ("Sentinel", "Landsat"),
    },
    "PSRI": {
        "name": "Plant Senescence Reflectance Index",
        "formula": "(RED - BLUE) / RED_EDGE2",
        "collections": ("Sentinel",),
    },
}

ALL_INDICES = list(INDEX_PRESETS.keys())


def parse_indices_arg(raw_indices: Optional[Sequence[str]], collection: str = "Sentinel") -> List[str]:
    """Normalize and validate requested spectral index names for the target collection."""
    if not raw_indices:
        return ["NDVI"]
    if isinstance(raw_indices, str):
        raw_indices = [raw_indices]

    parsed: List[str] = []
    for item in raw_indices:
        for token in str(item).replace(";", ",").split(","):
            name = token.strip().upper()
            if not name:
                continue
            if name not in INDEX_PRESETS:
                raise ValueError(f"Unknown index '{name}'. Supported: {ALL_INDICES}")
            if collection not in INDEX_PRESETS[name]["collections"]:
                raise ValueError(
                    f"Index '{name}' is only supported for {INDEX_PRESETS[name]['collections']}, not '{collection}'."
                )
            if name not in parsed:
                parsed.append(name)

    return parsed or ["NDVI"]


def compute_ee_indices(scaled_img: ee.Image, indices: Sequence[str]) -> ee.Image:
    """Compute one or more spectral index bands from a surface-reflectance-scaled image.

    Expected canonical band names on `scaled_img` (reflectance in ~[0, 1]):
    BLUE, GREEN, RED, NIR, SWIR1, SWIR2 (and RED_EDGE2 for Sentinel-2 PSRI).
    """
    bands: List[ee.Image] = []
    for idx in indices:
        if idx == "NDVI":
            b = scaled_img.normalizedDifference(["NIR", "RED"]).rename("NDVI")
        elif idx == "EVI":
            b = scaled_img.expression(
                "2.5 * (NIR - RED) / (NIR + 6.0 * RED - 7.5 * BLUE + 1.0)",
                {
                    "NIR": scaled_img.select("NIR"),
                    "RED": scaled_img.select("RED"),
                    "BLUE": scaled_img.select("BLUE"),
                },
            ).rename("EVI")
        elif idx == "SAVI":
            b = scaled_img.expression(
                "1.5 * (NIR - RED) / (NIR + RED + 0.5)",
                {"NIR": scaled_img.select("NIR"), "RED": scaled_img.select("RED")},
            ).rename("SAVI")
        elif idx == "NDMI":
            b = scaled_img.normalizedDifference(["NIR", "SWIR1"]).rename("NDMI")
        elif idx == "NDWI":
            b = scaled_img.normalizedDifference(["GREEN", "NIR"]).rename("NDWI")
        elif idx == "NBR":
            b = scaled_img.normalizedDifference(["NIR", "SWIR2"]).rename("NBR")
        elif idx == "BSI":
            b = scaled_img.expression(
                "((SWIR1 + RED) - (NIR + BLUE)) / ((SWIR1 + RED) + (NIR + BLUE))",
                {
                    "SWIR1": scaled_img.select("SWIR1"),
                    "RED": scaled_img.select("RED"),
                    "NIR": scaled_img.select("NIR"),
                    "BLUE": scaled_img.select("BLUE"),
                },
            ).rename("BSI")
        elif idx == "GNDVI":
            b = scaled_img.normalizedDifference(["NIR", "GREEN"]).rename("GNDVI")
        elif idx == "PSRI":
            re2 = scaled_img.select("RED_EDGE2")
            b = (
                scaled_img.expression(
                    "(RED - BLUE) / RED_EDGE2",
                    {
                        "RED": scaled_img.select("RED"),
                        "BLUE": scaled_img.select("BLUE"),
                        "RED_EDGE2": re2,
                    },
                )
                .updateMask(re2.abs().gt(1e-6))
                .rename("PSRI")
            )
        else:
            raise ValueError(f"Unsupported index: {idx}")
        bands.append(b)

    return ee.Image.cat(bands)
