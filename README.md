![TheroPoDa Logo](Logo.gif)

# 🦖 T(h)eroPoDa+ v3 — Time Series Extraction for Polygonal Data & Trend Analysis

[![License: MIT](./docs/mit.svg)](./LICENSE)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-00897b?logo=githubpages&logoColor=white)](https://lapig-ufg.github.io/TheroPoDa/)

> **Documentation & Visual Examples:** [https://lapig-ufg.github.io/TheroPoDa/](https://lapig-ufg.github.io/TheroPoDa/)

**TheroPoDa+** extracts cloud-masked median NDVI time series from **Sentinel-2** and **Landsat 8/9** in Google Earth Engine (GEE) for polygonal vector assets, stores incremental checkpoints in **SQLite**, applies seasonal gap-filling (`SeasConvFill`) and robust **STL + OLS** trend decomposition, and provides an **interactive Streamlit Dashboard** and **PyQt5 Desktop GUI**.

- **Author:** Vinícius Vieira Mesquita (`vinicius.mesquita@ufg.br`)
- **Co-author:** Leandro Leal Parente (`leandro.parente@opengeohub.org `)

---

## Architecture & Data Flow

```mermaid
flowchart TD
    subgraph GEE["1. Google Earth Engine Extraction"]
        direction LR
        ASSET["Vector Asset (Polygons)"] --> EXTR["theropoda.py (Parallel reduceRegion)"]
        MASK["mask_resolver.py (LULC Mask + Year Clamping)"] --> EXTR
        SAT["Sentinel-2 / Landsat 8-9"] --> EXTR
    end

    EXTR -->|"Incremental Checkpoint"| DB[("SQLite .db (table: observations)")]

    subgraph LOCAL["2. Local Time Series & Trend Analysis"]
        direction LR
        GF["trend_analysis.py (Pixel_used >= 70% + SeasConvFill)"] --> STL["STL Decomposition + OLS Regression"]
        STL --> PQ["Parquet (_trend_analysis.parquet)"]
    end

    DB --> GF

    subgraph UI["3. Interactive Interfaces"]
        direction LR
        DASH["dashboard.py (Streamlit Runner + STL + SQLite)"]
        GUI["gui.py (PyQt5 Desktop App)"]
        THERA["thera_animator.py (Mascot Monitor)"]
        THERA --> DASH
    end

    DB --> DASH
    PQ --> DASH
```

---

## Quickstart

### 1. Environment Setup

Using **`uv`** (recommended):
```bash
uv venv --python 3.10
uv sync --all-extras
uv run pip install 'git+https://github.com/openlandmap/scikit-map#egg=scikit-map[full]'
uv run earthengine authenticate
```

Using **WSL (Ubuntu/Debian with preinstalled GDAL/geospatial stack)**:
```powershell
wsl pip3 install --user --break-system-packages streamlit
wsl earthengine authenticate   # if not already authenticated
```

### 2. Run via Interactive Dashboard (Recommended)

```bash
# Local / Linux / macOS
streamlit run dashboard.py

# From Windows PowerShell using WSL
wsl python3 -m streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
```

Open **http://localhost:8501**:
- **🚀 Executar Pipeline:** Configure all CLI parameters, start extraction in the background, and watch real-time auto-scrolling logs + the **Thera** mascot monitor (`Thera/animations_web/`).
- **📊 Tabela & Tendências:** Filter polygons by `trend_pv`, `r2`, and trend direction; inspect distributions and export CSV.
- **📈 Série Temporal por Polígono:** Inspect the 4-panel **STL Decomposition** (`Observed`, `Trend + OLS`, `Season`, `Resid`) with optional raw `.db` overlay.
- **🗄️ Explorador do Banco SQLite:** Query `observations` (or legacy `restoration`) directly with optional `WHERE` clauses.

### 3. Run via CLI

```bash
# Unmasked Sentinel-2 extraction
python3 main.py \
  -a users/vieiramesquita/LAPIG_FieldSamples/lapig_goias_fieldwork_2022_50m \
  -id ID_POINTS \
  -c Sentinel \
  -o LAPIG_S2_NDVI \
  -start 2019-01-01 \
  -end 2026-01-01

# Custom LULC mask with multiple classes (automatic year detection & clamping)
python3 main.py \
  -a users/vieiramesquita/LAPIG_FieldSamples/lapig_goias_fieldwork_2022_50m \
  -id ID_POINTS \
  -c Sentinel \
  -o LAPIG_Pasture_Grasslands \
  -start 2020-01-01 \
  -end 2026-01-01 \
  -p ee-vieiramesquita \
  -m projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3 \
  -mc 15 11 12
```

### 4. Run via Desktop GUI (PyQt5)

```bash
python3 gui.py
```

---

## CLI Reference

| Flag | Long Flag | Required | Default | Description |
|:---|:---|:---:|:---|:---|
| `-a` | `--asset` | Yes | — | Earth Engine Vector Asset (`FeatureCollection`) |
| `-id` | `--id_field` | Yes | — | Unique polygon ID column (must have 1 unique value per feature) |
| `-c` | `--collection` | Yes | — | `Sentinel` or `Landsat` |
| `-o` | `--output_name` | Yes | — | Base output filename |
| `-of` | `--output_folder` | No | `""` | Output directory |
| `-start` | `--start_date` | Yes | — | Start date (`YYYY-MM-DD`) |
| `-end` | `--end_date` | Yes | — | End date (`YYYY-MM-DD`) |
| `-w` | `--window` | No | `15` (S2) / `16` (LS) | Temporal standardization window (days) |
| `-n` | `--n_cores` | No | `12` | Parallel `joblib` workers |
| `-p` | `--project` | No | `None` | Google Cloud / Earth Engine project ID |
| `-m` | `--mask` | No | `None` | GEE `Image`/`ImageCollection` asset or preset (`mapbiomas-pasture`, `mapbiomas-pasture-grasslands`) |
| `-mc` | `--mask-classes` | No | `None` | Class ID(s) to keep (e.g. `15 11 12` or `15,11,12`) |
| — | `--mask-start-year` | No | `None` | First year for multiband masks whose band names lack years |
| — | `--mask-band` | No | `None` | Explicit band name for static single-band extraction |

---

## AI-Friendly Reference (Module Map & Invariants)

### Repository Layout

| File | Responsibility | Key Entrypoints / Symbols |
|:---|:---|:---|
| [`main.py`](main.py) | CLI parser & pipeline orchestrator | `run_analysis(...)`, `build_arg_parser()` |
| [`theropoda.py`](theropoda.py) | GEE NDVI extraction & SQLite checkpointing | `init_ee(project)`, `getTimeSeries(...)`, `build_id_list(...)`, `run(...)` |
| [`mask_resolver.py`](mask_resolver.py) | Dynamic GEE mask inspection & year clamping | `inspect_mask_spec(...)`, `parse_year_bands(...)`, `build_ee_mask(...)` |
| [`trend_analysis.py`](trend_analysis.py) | Window aggregation, `SeasConvFill`, `STL`, `OLS` | `extract_ts(...)`, `gapfill(...)`, `sm_trend(...)`, `run(...)` |
| [`dashboard.py`](dashboard.py) | Streamlit runner, STL 4-panel viewer & SQLite explorer | `main()`, `_render_runner_tab()`, `_render_live_log()`, `_render_thera_sidebar()` |
| [`thera_animator.py`](thera_animator.py) | State machine & GIF loader for `Thera/animations_web/` | `load_thera_sprites()`, `resolve_thera_state(...)`, `count_log_errors(...)` |
| [`gui.py`](gui.py) | PyQt5 desktop frontend | `TheroPoDaGUI`, `AnalysisThread` |

### Key Design Invariants
1. **Unique Polygon IDs (`--id_field`):** Every feature in the input GEE Asset or local vector file must have a **strictly unique** value in `--id_field`. Duplicate IDs overwrite/merge geometry mappings and corrupt per-polygon checkpointing and trend aggregation. If your file lacks a unique ID column, create one beforehand (e.g. `gdf["ID_UNICO"] = range(1, len(gdf) + 1)`).
2. **Lazy GEE Initialization:** `theropoda.init_ee(project)` is never executed on module import; it initializes lazily inside execution functions so `--help`, tests, and UIs work without active GEE sessions.
2. **Dynamic Mask Year Clamping:** `inspect_mask_spec()` inspects `bandNames()` or `system:time_start` once before parallel workers start. During extraction, `clamped_year = clamp(img_year, min_year, max_year)` ensures out-of-range satellite years (e.g. `2025–2026` with maps up to `2024`) automatically use the nearest available map.
3. **SQLite Schema & Resume:** Extraction writes to table `observations` (with WAL mode and `timeout=60`). Downstream readers (`main.py`, `trend_analysis.py`, `dashboard.py`) check `observations` and fall back to legacy `restoration`. Completed IDs are pre-filtered once in `theropoda.run()`.
4. **Empty vs. Failed Polygons:** Polygons with zero valid pixels after cloud/LULC masking are logged to `*_empty_polygon.txt` without triggering `bestEffort=True`; only GEE exceptions retry with `bestEffort=True` and log to `*_errors_polygon.txt`.
5. **Seasonality Calculation:** `season_size = max(3, round(365 / eff_window))` represents one annual cycle for `SeasConvFill` and `STL(robust=True)`.

### Verification Commands

```bash
python3 -m py_compile mask_resolver.py theropoda.py trend_analysis.py main.py gui.py dashboard.py thera_animator.py
python3 main.py --help
```

---

## Changelog

### v3.0.0 (2026-11)
- **Local Vector Support (No GEE Upload Required):** `-a` / `--asset` now accepts local `.gpkg`, `.shp`, `.geojson`, `.parquet`, and `.zip` files directly via `geopandas` (`is_local_vector` / `load_local_geometries`), with upload support in the Streamlit Dashboard and file picker in `gui.py`.
- **Unified Branch (`v3` / `main`):** Merged CLI, PyQt5 GUI (`gui.py`), `uv` / WSL setup, and dynamic LULC masking into a single codebase.
- **Dynamic LULC Masks & Multi-Class Support (`mask_resolver.py`):** Added `--mask` (`-m`) for presets (`mapbiomas-pasture`, `mapbiomas-pasture-grasslands`) or custom GEE `Image`/`ImageCollection` assets, `--mask-classes` (`-mc`), `--mask-start-year`, `--mask-band`, and automatic year clamping (`[min_year, max_year]`).
- **Interactive Streamlit Dashboard (`dashboard.py`) + Thera Monitor (`thera_animator.py`):** Added background pipeline runner with real-time auto-scrolling logs (F5-safe via `.theropoda_last_run.json`), `trend_m` distribution/significance plots, 3-panel STL decomposition, SQLite explorer, and 9 animated Thera mascot states.
- **Extraction & Reliability Fixes:** Applied GEE `.filterDate(start_date, end_date)` during extraction, removed `.toList(imgCol.size())` overhead, pre-filtered completed IDs once in `theropoda.run()`, enabled SQLite WAL mode + `timeout=60`, separated empty-after-mask polygons (`*_empty_polygon.txt`) from real GEE errors, renamed SQLite table to `observations` (with `restoration` fallback), and fixed `--window` / `season_size` parsing in `main.py`.
- **Documentation & Packaging:** Updated MkDocs Material site (`https://lapig-ufg.github.io/TheroPoDa/`), `pyproject.toml`, `LICENSE`, and `CITATION.cff`.

### v2.0.0
- Added Landsat 8/9 support alongside Sentinel-2 (`Cloud Score+`), `--collection`, `--start_date`, `--end_date`, `--window`, and `STL` + `OLS` trend analysis (`trend_analysis.py`).

### v1.1.0
- Initial Sentinel-2 median NDVI extraction to SQLite and `SeasConvFill` gap-filling.

---

## License & Authors

Licensed under the [MIT License](./LICENSE).

- **Vinícius Vieira Mesquita** — LAPIG / UFG (`vinicius.mesquita@ufg.br`)
- **Leandro Leal Parente** — (`leal.parente@gmail.com`)

