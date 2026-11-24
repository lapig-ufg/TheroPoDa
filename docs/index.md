![TheroPoDa Logo](assets/Logo.jpg)

# 🦖 T(h)eroPoDa+ v3 — Time Series Extraction for Polygonal Data & Trend Analysis

**TheroPoDa+** is an open-source toolkit for extracting cloud-masked median NDVI time series from **Sentinel-2** and **Landsat 8/9** in Google Earth Engine (GEE) across polygonal vector assets, storing incremental checkpoints in **SQLite** (`observations`), performing seasonal gap-filling (`SeasConvFill`) and **STL + OLS** trend analysis, and exploring results in an **interactive Streamlit Dashboard** or **PyQt5 Desktop GUI**.

- **Author:** Vinícius Vieira Mesquita (`vinicius.mesquita@ufg.br`) — LAPIG / UFG
- **Co-author:** Leandro Leal Parente (`leal.parente@gmail.com`)
- **Version:** `3.0.0` | **License:** MIT

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

## Installation

### Option A — Using `uv` (Recommended)

```bash
uv venv --python 3.10
uv sync --all-extras
uv run pip install 'git+https://github.com/openlandmap/scikit-map#egg=scikit-map[full]'
uv run earthengine authenticate
```

### Option B — WSL (Ubuntu / Debian)

```powershell
wsl pip3 install --user --break-system-packages streamlit
wsl earthengine authenticate
```

---

## Quick CLI Example

```bash
python3 main.py \
  -a users/vieiramesquita/LAPIG_FieldSamples/lapig_goias_fieldwork_2022_50m \
  -id ID_POINTS \
  -c Sentinel \
  -o LAPIG_Pasture_S2_NDVI \
  -start 2019-01-01 \
  -end 2026-01-01 \
  -p ee-vieiramesquita \
  -m projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3 \
  -mc 15
```
