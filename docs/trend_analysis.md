# Trend Analysis Module (`theropoda/trends.py`)

`theropoda/trends.py` converts irregular, cloud-gapped SQLite polygon observations into standardized, gap-filled time series and statistically robust trend metrics saved in `*_trend_analysis.parquet`.

---

## Pipeline Overview

1. **Quality Filtering (`Pixel_used >= 70%`) & Window Aggregation (`extract_ts`):**
   - Computes valid pixel ratio `Pixel_used = (Pixel_Count / Total_Pixels) * 100` per scene.
   - Discards partially cloud-contaminated scenes (`Pixel_used < 70%`) and averages valid observations inside standardized non-leap temporal windows (`15` days for Sentinel-2 → `season_size = 24`; `16` days for Landsat → `season_size = 23`).
2. **Observed-Span Slicing & Gap-Filling (`gapfill`):**
   - Identifies the first and last valid temporal windows (`[first_idx : last_idx + 1]`) for each polygon and spectral index.
   - Applies `scikit-map`'s **`SeasConvFill`** strictly within the observed span, leaving `NaN` outside `[first_idx, last_idx]` so no synthetic history is extrapolated before or after real satellite observations.
3. **Minimum Series Length Gate (`2 * season_size`):**
   - Requires at least **2 full seasonal cycles** (~24 months; `48` windows at 15-day step) to reliably separate seasonality from long-term trend. Polygons with shorter observed spans are safely skipped.
4. **Robust STL + OLS Regression (`sm_trend`):**
   - Decomposes the reconstructed span with `statsmodels.tsa.seasonal.STL(..., period=season_size, robust=True)` into `Trend`, `Season`, and `Resid`.
   - Fits **Ordinary Least Squares (`OLS`)** on the STL `Trend` over normalized time $x \in [0, 1]$.

---

## Output Metrics (`*_trend_analysis.parquet`)

| Column | Description |
|:---|:---|
| `id_pol` | Unique polygon identifier (`--id_field`) |
| `index_name` | Spectral index name (`NDVI`, `EVI`, `NDMI`, `PSRI`, etc.) |
| `intercept_m`, `intercept_sd`, `intercept_tv`, `intercept_pv` | OLS baseline intercept (estimated initial STL trend level), standard error, *t*-value, and *p*-value |
| `trend_m`, `trend_sd`, `trend_tv`, `trend_pv` | OLS linear slope across the observed span ($x \in [0, 1]$), standard error, *t*-value, and *p*-value |
| `r2` | Coefficient of determination ($R^2$) of linear OLS against the non-linear STL trend |
| `diff_trend` | Net structural shift ($\text{Trend}_{\text{last}} - \text{Trend}_{\text{first}}$) |
| `d_YYYY-MM-DD` | Standardized gap-filled series values (`NaN` outside the polygon's observed span) |
