# Dynamic LULC Masks & CLI Reference

TheroPoDa+ v3 unifies all masking workflows into `mask_resolver.py`, supporting presets, custom `ee.Image` assets, and `ee.ImageCollection` assets with **multi-class filtering** and **automatic year clamping**.

---

## How Automatic Year Detection & Clamping Work

When `--mask` (`-m`) is provided, `inspect_mask_spec()` inspects the asset **once** before launching parallel workers:

1. **Multiband `ee.Image` with years in band names** (e.g. MapBiomas `classification_1985` … `classification_2025`): extracts `{year: band_name}` automatically via regex.
2. **Multiband `ee.Image` without years in band names** (e.g. `b1, b2, ...`): pass `--mask-start-year 1985` to map bands sequentially, or `--mask-band <name>` for a static band.
3. **`ee.ImageCollection`:** inspects `system:time_start` (or `year` property) to resolve annual images.
4. **Single-band `ee.Image`:** applied statically across all years.

During extraction, satellite image years outside `[min_year, max_year]` are automatically clamped:
```python
clamped_year = ee.Number(img_year).max(spec.min_year).min(spec.max_year).toInt()
```
For example, extracting **2019–2026** with a mask covering **1985–2024** uses exact annual maps for `2019–2024` and automatically applies the **2024** map for `2025` and `2026`.

---

## Examples

### Presets
```bash
# MapBiomas Collection 11 Pasture (class 15)
python3 main.py -a <ASSET> -id ID_POINTS -c Sentinel -o out_pasture -start 2019-01-01 -end 2026-01-01 -m mapbiomas-pasture

# MapBiomas Collection 10 Pasture (15) + Grasslands (11, 12 in SC/RS/Pantanal)
python3 main.py -a <ASSET> -id ID_POINTS -c Sentinel -o out_grass -start 2019-01-01 -end 2026-01-01 -m mapbiomas-pasture-grasslands
```

### Custom Asset + Multiple Classes
```bash
python3 main.py \
  -a <ASSET> \
  -id ID_POINTS \
  -c Sentinel \
  -o out_custom \
  -start 2020-01-01 \
  -end 2026-01-01 \
  -m projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3 \
  -mc 15 11 12
```
