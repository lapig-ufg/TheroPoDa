# `mask_resolver.py`

Dynamic LULC mask resolution and year-band mapping for Google Earth Engine.

## Key Symbols

- **`MASK_PRESETS`**: Built-in shortcuts (`mapbiomas-pasture`, `mapbiomas-pasture-grasslands`).
- **`MaskSpec`**: Frozen dataclass holding `asset_id`, `mode` (`multiband_years`, `image_collection`, `static_image`, `grasslands_preset`), `classes`, `year_to_band`, `min_year`, and `max_year`.
- **`parse_classes_arg(raw_classes)`**: Normalizes CLI/GUI class lists (e.g., `["15", "11,12"]` → `[15, 11, 12]`).
- **`parse_year_bands(band_names, mask_start_year=None, mask_band=None)`**: Pure helper that infers `{year: band_name}` from band names or sequential `--mask-start-year`.
- **`inspect_mask_spec(mask_input, classes=None, mask_start_year=None, mask_band=None)`**: Performs a single GEE metadata lookup at startup and returns a `MaskSpec`.
- **`build_ee_mask(spec, img_year, geometry)`**: Server-side helper that clamps `img_year` to `[min_year, max_year]`, selects the matching band/image, and filters target classes via `.eq()` / `.remap()`.
