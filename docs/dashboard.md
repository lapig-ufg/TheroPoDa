# Interactive Streamlit Dashboard & Thera Monitor

Launch the dashboard locally (or from WSL):

```bash
streamlit run dashboard.py
# Or in WSL:
wsl python3 -m streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
```

Open **http://localhost:8501** in your browser.

---

## Dashboard Tabs

| Tab | Features |
|:---|:---|
| **🚀 Executar Pipeline** | Configure all CLI parameters, run extraction in the background, and monitor real-time auto-scrolling logs (survives browser F5 via `.theropoda_last_run.json`). |
| **📊 Tabela & Tendências** | KPI cards, `trend_m` (OLS slope) histogram, `trend_pv` vs `trend_m` scatter plot, interactive filters, and CSV export. |
| **📈 Série Temporal por Polígono** | 3-panel **STL Decomposition** (`Observed + Trend STL + OLS`, `Season`, `Resid`) with optional raw `.db` points and automatic `--id_field` detection. |
| **🗄️ Explorador do Banco SQLite** | Inspect the `observations` (or legacy `restoration`) table with custom SQL `WHERE` filters and CSV download. |

---

## 🦖 Thera Mascot Monitor

The sidebar hosts **Thera**, an animated pixel-art companion driven by `thera_animator.py` and `Thera/animations_web/*.gif`:

| State | Trigger | Preview |
|:---|:---|:---:|
| **Sleeping** (`sleeping.gif`) | Idle / waiting for jobs | — |
| **Waking** (`waking.gif`) | Pipeline starts | — |
| **Running** (`running.gif`) / **Lot** (`lot.gif`) | GEE extraction (`lot.gif` for `> 1000` polygons) | — |
| **Critical Damage** (`damage.gif`) | New `ERROR` detected in log, then returns to running | — |
| **JetPack** (`jetpack.gif`) | Trend analysis stage (`STL` + `OLS`) | ![JetPack](assets/thera_jetpack.gif){ width="120" } |
| **Tired → Gonna Sleep** | Pipeline completes (`exit code 0`) | — |
| **Analysing** (`analysing.gif`) | Interacting with Table, Time Series, or SQLite tabs | ![Analysing](assets/thera_analysing.gif){ width="120" } |
