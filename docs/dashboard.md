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

## 🦖 Thera Mascot Monitor (All 9 Animated States)

The sidebar hosts **Thera**, an animated pixel-art companion driven by `thera_animator.py` and `Thera/animations_web/*.gif`:

| State | Trigger | Animation |
|:---|:---|:---:|
| **Sleeping** (`sleeping.gif`) | Idle / waiting for jobs | ![Sleeping](assets/thera_sleeping.gif){ width="110" } |
| **Waking** (`waking.gif`) | Pipeline starts | ![Waking](assets/thera_waking.gif){ width="110" } |
| **Running** (`running.gif`) | Standard GEE extraction | ![Running](assets/thera_running.gif){ width="110" } |
| **Lot** (`lot.gif`) | Large batch (`> 1000` polygons) | ![Lot](assets/thera_lot.gif){ width="110" } |
| **Critical Damage** (`damage.gif`) | New `ERROR` detected in log, then returns to running | ![Damage](assets/thera_damage.gif){ width="110" } |
| **JetPack** (`jetpack.gif`) | Trend analysis stage (`STL` + `OLS`) | ![JetPack](assets/thera_jetpack.gif){ width="110" } |
| **Tired** (`tired.gif`) | Pipeline completes (`exit code 0`) | ![Tired](assets/thera_tired.gif){ width="110" } |
| **Gonna Sleep** (`gonna_sleep.gif`) | Transition back to idle after `tired` | ![Gonna Sleep](assets/thera_gonna_sleep.gif){ width="110" } |
| **Analysing** (`analysing.gif`) | Interacting with Table, Time Series, or SQLite tabs | ![Analysing](assets/thera_analysing.gif){ width="110" } |
