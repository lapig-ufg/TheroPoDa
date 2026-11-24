# Visual Examples

Results below were generated using **TheroPoDa+ v3** on the LAPIG Goiás fieldwork sample dataset (`460` polygons, Sentinel-2 `2019-01-01` to `2026-01-01`, MapBiomas Collection 11 Pasture mask `-mc 15`).

---

## 1. Landscape Trend Distribution (`trend_m` & `trend_pv`)

Distribution of the OLS trend slope (`trend_m`) and statistical significance (`trend_pv` vs. `trend_m`, colored by `R²`) across all extracted polygons:

![Trend Distribution](assets/trend_distribution.png)

---

## 2. Per-Polygon STL Decomposition (`Observed`, `Season`, `Resid`)

3-panel STL decomposition for an individual polygon (`ID_POINTS = 307`), combining:
- **Top:** Raw GEE observations (`.db`), gap-filled standardized series (`SeasConvFill`), non-linear `STL` trend, and `OLS` linear slope.
- **Middle:** Extracted seasonal cycle (`Season`).
- **Bottom:** Residual noise (`Resid`).

![STL Decomposition Example](assets/stl_example.png)
