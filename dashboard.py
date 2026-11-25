"""Interactive Streamlit dashboard for TheroPoDa execution, SQLite (.db), and Trend Parquet outputs."""

import datetime
import glob
import html
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from statsmodels.tsa.seasonal import STL
import streamlit as st
import streamlit.components.v1 as components

from theropoda.animator import (
    STATE_LABELS,
    build_thera_canvas_html,
    count_log_errors,
    load_thera_sprites,
    resolve_thera_state,
)
from theropoda.indices import ALL_INDICES, INDEX_PRESETS

_ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
st.set_page_config(
    page_title="TheroPoDa Dashboard",
    page_icon=_ICON_PATH if os.path.exists(_ICON_PATH) else "🦖",
    layout="wide",
)


def normalize_path(path: str) -> str:
    """Convert Windows paths (e.g. E:\\foo) to /mnt/e/foo when running under WSL/Linux."""
    cleaned = path.strip().strip('"').strip("'")
    if os.name != "nt":
        match = re.match(r"^([A-Za-z]):[\\/](.*)$", cleaned)
        if match:
            drive = match.group(1).lower()
            rest = match.group(2).replace("\\", "/")
            return f"/mnt/{drive}/{rest}"
    return cleaned


def discover_files(base_dir: str) -> Tuple[List[str], List[str]]:
    """Find SQLite .db and trend analysis .parquet files in base_dir."""
    base_dir = normalize_path(base_dir)
    dbs = sorted(glob.glob(os.path.join(base_dir, "*.db")))
    parquets = sorted(glob.glob(os.path.join(base_dir, "*_trend_analysis.parquet")))
    return dbs, parquets


@st.cache_data(show_spinner=False)
def get_cached_thera_sprites():
    return load_thera_sprites(size=240)


@st.cache_data(show_spinner=False)
def load_parquet(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False)
def load_sqlite_tables(db_path: str) -> List[str]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return [r[0] for r in rows]


@st.cache_data(show_spinner=False)
def load_sqlite_query(db_path: str, query: str, params: Tuple = ()) -> pd.DataFrame:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        return pd.read_sql_query(query, con, params=params)


_RUNNER_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".theropoda_last_run.json")


def _is_pid_running(pid: Optional[int]) -> bool:
    """Check whether an OS process ID is still alive."""
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _save_runner_state(state: Dict) -> None:
    try:
        with open(_RUNNER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass


def _load_runner_state() -> Optional[Dict]:
    if not os.path.exists(_RUNNER_STATE_FILE):
        return None
    try:
        with open(_RUNNER_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _stop_process_tree(proc, pid: Optional[int]) -> None:
    """Terminate the runner process and all child worker processes."""
    target_pid = proc.pid if proc is not None else pid
    if not target_pid:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(int(target_pid))], capture_output=True)
        else:
            os.killpg(int(target_pid), signal.SIGTERM)
    except OSError:
        if proc is not None:
            try:
                proc.terminate()
            except OSError:
                pass


def _clean_generated_files(output_dir: str, output_name: str) -> int:
    """Remove generated .db, .parquet, .pq, .txt, and .log files for output_name."""
    base = os.path.join(normalize_path(output_dir) if output_dir.strip() else os.getcwd(), output_name.strip())
    targets = [
        f"{base}.db",
        f"{base}.db-shm",
        f"{base}.db-wal",
        f"{base}_polygonList.txt",
        f"{base}_errors_polygon.txt",
        f"{base}_empty_polygon.txt",
        f"{base}_trend_analysis.parquet",
        f"{base}_trend_analysis.pq",
        f"{base}_run.log",
    ]
    removed = 0
    for path in targets:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
        elif os.path.exists(path):
            os.remove(path)
            removed += 1
    if os.path.exists(_RUNNER_STATE_FILE):
        os.remove(_RUNNER_STATE_FILE)
    return removed


def _render_runner_tab(default_dir: str) -> None:
    """Render the pipeline parameter form and background log monitor."""
    st.subheader("Configurar e Executar Extração + Análise de Tendência")

    with st.form("theropoda_runner_form"):
        c1, c2 = st.columns(2)
        asset = c1.text_input(
            "Vetor: GEE Asset OU arquivo local (.gpkg, .shp, .geojson, .parquet, .zip) (-a)",
            value="users/vieiramesquita/LAPIG_FieldSamples/lapig_goias_fieldwork_2022_50m",
        )
        id_field = c2.text_input("Coluna de ID (-id)", value="ID_POINTS")
        uploaded_vector = st.file_uploader(
            "Ou envie um arquivo vetorial local (opcional — substitui o campo acima se enviado)",
            type=["gpkg", "geojson", "json", "parquet", "geoparquet", "zip"],
        )

        c3, c4, c5 = st.columns(3)
        collection = c3.selectbox("Coleção (-c)", ["Sentinel", "Landsat"])
        output_name = c4.text_input("Nome de saída (-o)", value="LAPIG_Pasture_S2_NDVI_Monitoring_FieldWork")
        output_folder = c5.text_input("Pasta de saída (-of)", value=default_dir)

        c6, c7, c8, c9 = st.columns(4)
        start_date = c6.date_input("Início (-start)", value=datetime.date(2019, 1, 1))
        end_date = c7.date_input("Fim (-end)", value=datetime.date(2026, 1, 1))
        window = c8.number_input("Janela em dias (-w)", min_value=1, max_value=60, value=15)
        n_cores = c9.number_input("Núcleos (-n)", min_value=1, max_value=64, value=12)

        project = st.text_input("Projeto GEE (-p, opcional)", value="ee-vieiramesquita")

        selected_indices = st.multiselect(
            "Índices Espectrais (-i)",
            options=ALL_INDICES,
            default=["NDVI"],
            help="Sentinel-2 aplica fator de escala 0.0001; Landsat 8/9 aplica 0.0000275 - 0.2. PSRI é exclusivo do Sentinel-2.",
        )

        st.markdown("**Máscara de Uso e Cobertura (opcional)**")
        m1, m2 = st.columns(2)
        mask_mode = m1.selectbox(
            "Modo da Máscara (-m)",
            ["Sem máscara", "mapbiomas-pasture", "mapbiomas-pasture-grasslands", "Asset customizado"],
        )
        custom_mask = m2.text_input(
            "Asset da Máscara (quando 'Asset customizado')",
            value="projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3",
        )

        m3, m4, m5 = st.columns(3)
        mask_classes = m3.text_input("Classes (-mc, separadas por vírgula ou espaço)", value="15")
        mask_start_year = m4.text_input("Ano inicial (--mask-start-year, opcional)", value="")
        mask_band = m5.text_input("Banda estática (--mask-band, opcional)", value="")

        submitted = st.form_submit_button("🚀 Iniciar Processamento", type="primary")

    if submitted:
        norm_out_dir = normalize_path(output_folder) if output_folder.strip() else os.getcwd()
        os.makedirs(norm_out_dir, exist_ok=True)

        if uploaded_vector is not None:
            resolved_asset = os.path.join(norm_out_dir, uploaded_vector.name)
            with open(resolved_asset, "wb") as uf:
                uf.write(uploaded_vector.getbuffer())
        else:
            resolved_asset = normalize_path(asset)

        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        cmd = [
            sys.executable,
            "-u",
            script_path,
            "-a", resolved_asset,
            "-id", id_field.strip(),
            "-c", collection,
            "-o", output_name.strip(),
            "-of", norm_out_dir,
            "-start", start_date.strftime("%Y-%m-%d"),
            "-end", end_date.strftime("%Y-%m-%d"),
            "-w", str(int(window)),
            "-n", str(int(n_cores)),
        ]
        if project.strip():
            cmd.extend(["-p", project.strip()])
        if selected_indices:
            cmd.extend(["-i", *selected_indices])

        if mask_mode == "Asset customizado" and custom_mask.strip():
            cmd.extend(["-m", custom_mask.strip()])
        elif mask_mode in ("mapbiomas-pasture", "mapbiomas-pasture-grasslands"):
            cmd.extend(["-m", mask_mode])

        if mask_mode != "Sem máscara" and mask_classes.strip():
            classes_tokens = [t.strip() for t in mask_classes.replace(",", " ").split() if t.strip()]
            if classes_tokens:
                cmd.extend(["-mc", *classes_tokens])
        if mask_start_year.strip().isdigit():
            cmd.extend(["--mask-start-year", mask_start_year.strip()])
        if mask_band.strip():
            cmd.extend(["--mask-band", mask_band.strip()])

        log_path = os.path.join(norm_out_dir, f"{output_name.strip()}_run.log")
        log_file = open(log_path, "w", encoding="utf-8", buffering=1)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        popen_kwargs = {"stdout": log_file, "stderr": subprocess.STDOUT, "env": env}
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **popen_kwargs)

        st.session_state["runner_pid"] = proc.pid
        st.session_state["runner_proc"] = proc
        st.session_state["runner_log"] = log_path
        st.session_state["runner_cmd"] = " ".join(cmd)
        st.session_state["runner_cache_cleared"] = False
        st.session_state["thera_waking_until"] = datetime.datetime.now().timestamp() + 2.5
        st.session_state["thera_last_errors"] = 0
        st.session_state["thera_damage_until"] = 0.0
        st.session_state["thera_tired_until"] = 0.0
        st.session_state["thera_gonna_sleep_until"] = 0.0
        _save_runner_state({"pid": proc.pid, "log_path": log_path, "cmd": " ".join(cmd)})
        st.success(f"Processamento iniciado (PID {proc.pid}). Log: `{log_path}`")
        st.rerun()

    ctrl_col1, ctrl_col2 = st.columns(2)
    if ctrl_col1.button("⏹️ Parar Processamento", use_container_width=True):
        _stop_process_tree(st.session_state.get("runner_proc"), st.session_state.get("runner_pid"))
        st.warning("Sinal de interrupção enviado para o processo e seus workers.")
        st.rerun()
    if ctrl_col2.button("🗑️ Limpar Arquivos Gerados", use_container_width=True):
        removed = _clean_generated_files(output_folder, output_name)
        for key in ("runner_proc", "runner_pid", "runner_log", "runner_cmd"):
            st.session_state.pop(key, None)
        st.cache_data.clear()
        st.success(f"{removed} arquivo(s)/pasta(s) de `{output_name}` removidos.")
        st.rerun()

    _render_live_log()


@st.fragment(run_every=2)
def _render_live_log() -> None:
    """Poll the background process and stream the tail of the log every 2 seconds."""
    if "runner_log" not in st.session_state:
        saved = _load_runner_state()
        if saved and saved.get("log_path"):
            st.session_state["runner_pid"] = saved.get("pid")
            st.session_state["runner_log"] = saved.get("log_path")
            st.session_state["runner_cmd"] = saved.get("cmd", "")
        else:
            return

    proc = st.session_state.get("runner_proc")
    pid = st.session_state.get("runner_pid")
    log_path = st.session_state["runner_log"]

    if proc is not None:
        status_code = proc.poll()
        running = status_code is None
    else:
        running = _is_pid_running(pid)
        status_code = None if running else 0

    col_s1, col_s2 = st.columns([3, 1])
    if running:
        col_s1.info(f"⏳ Em execução — atualizando log automaticamente a cada 2s (PID {pid})")
        if col_s2.button("⏹️ Interromper"):
            _stop_process_tree(proc, pid)
            st.rerun()
    elif status_code == 0:
        if not st.session_state.get("runner_cache_cleared"):
            st.cache_data.clear()
            st.session_state["runner_cache_cleared"] = True
        col_s1.success("✅ Processamento finalizado (exit code 0).")
        if col_s2.button("🔄 Recarregar Dados"):
            st.cache_data.clear()
            st.rerun()
    else:
        col_s1.error(f"❌ Processamento encerrado com código {status_code}.")

    with st.expander("Comando executado", expanded=False):
        st.code(st.session_state.get("runner_cmd", ""), language="bash")

    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        escaped = html.escape("".join(lines[-120:]))
        components.html(
            f"""
            <pre id="log-box" style="
                height: 340px;
                overflow-y: auto;
                background: #0e1117;
                color: #e6edf3;
                padding: 12px;
                border-radius: 6px;
                border: 1px solid #30363d;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 12px;
                line-height: 1.45;
                margin: 0;
                white-space: pre-wrap;
                word-break: break-word;
            ">{escaped}</pre>
            <script>
                const box = document.getElementById("log-box");
                if (box) {{ box.scrollTop = box.scrollHeight; }}
            </script>
            """,
            height=360,
        )


@st.fragment(run_every=2)
def _render_thera_sidebar(active_tab: str, thera_override: str) -> None:
    """Update Thera mascot animation automatically every 2s according to pipeline state."""
    if "runner_log" not in st.session_state:
        saved = _load_runner_state()
        if saved and saved.get("log_path"):
            st.session_state["runner_pid"] = saved.get("pid")
            st.session_state["runner_log"] = saved.get("log_path")
            st.session_state["runner_cmd"] = saved.get("cmd", "")

    proc = st.session_state.get("runner_proc")
    pid = st.session_state.get("runner_pid")
    log_path = st.session_state.get("runner_log")
    if proc is not None:
        status_code = proc.poll()
        is_running = status_code is None
    else:
        is_running = _is_pid_running(pid)
        status_code = None if is_running else (0 if log_path else None)

    log_text = ""
    if log_path and os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            log_text = "".join(f.readlines()[-120:])

    now_ts = datetime.datetime.now().timestamp()
    err_count = count_log_errors(log_text)
    if is_running and err_count > st.session_state.get("thera_last_errors", err_count):
        st.session_state["thera_damage_until"] = now_ts + 2.5
    st.session_state["thera_last_errors"] = err_count

    if not is_running and status_code == 0 and st.session_state.get("thera_was_running"):
        st.session_state["thera_tired_until"] = now_ts + 12.0
        st.session_state["thera_gonna_sleep_until"] = now_ts + 18.0
    st.session_state["thera_was_running"] = is_running

    if thera_override != "Auto (Estado Real)":
        thera_state = thera_override
    else:
        thera_state = resolve_thera_state(
            active_tab=active_tab,
            running=is_running,
            status_code=status_code,
            log_text=log_text,
            now=now_ts,
            waking_until=st.session_state.get("thera_waking_until", 0.0),
            damage_until=st.session_state.get("thera_damage_until", 0.0),
            tired_until=st.session_state.get("thera_tired_until", 0.0),
            gonna_sleep_until=st.session_state.get("thera_gonna_sleep_until", 0.0),
        )

    sprites = get_cached_thera_sprites()
    if sprites:
        components.html(build_thera_canvas_html(sprites, thera_state, size=220), height=260)


def main():
    header_icon, header_title = st.columns([1, 14], vertical_alignment="center")
    if os.path.exists(_ICON_PATH):
        header_icon.image(_ICON_PATH, width=56)
    header_title.title("TheroPoDa+ Dashboard")
    header_title.caption("Execução de parâmetros, exploração tabular, banco SQLite e análise de tendência NDVI")

    default_dir = os.environ.get("THEROPODA_DATA_DIR", os.getcwd())
    nav_options = [
        "🚀 Executar Pipeline",
        "📊 Tabela & Tendências",
        "📈 Série Temporal por Polígono",
        "🗄️ Explorador do Banco SQLite",
    ]
    active_tab = st.segmented_control(
        "Navegação",
        options=nav_options,
        default=nav_options[0],
        label_visibility="collapsed",
    ) or nav_options[0]

    with st.sidebar:
        st.subheader("Thera Monitor")
        preview_options = ["Auto (Estado Real)"] + list(STATE_LABELS.keys())
        thera_override = st.selectbox(
            "Animação",
            options=preview_options,
            format_func=lambda k: k if k == "Auto (Estado Real)" else STATE_LABELS[k],
        )
        _render_thera_sidebar(active_tab, thera_override)

        st.divider()
        st.header("Fonte de Dados")
        data_dir = st.text_input("Diretório dos resultados", value=default_dir)
        dbs, parquets = discover_files(data_dir)

        selected_parquet = st.selectbox(
            "Arquivo de Tendência (.parquet)",
            options=["(Nenhum)"] + parquets,
            index=1 if parquets else 0,
        )
        selected_db = st.selectbox(
            "Banco SQLite (.db)",
            options=["(Nenhum)"] + dbs,
            index=1 if dbs else 0,
        )

    df_trend = load_parquet(selected_parquet) if selected_parquet != "(Nenhum)" else None
    has_db = selected_db != "(Nenhum)"

    if active_tab == nav_options[0]:
        _render_runner_tab(data_dir)
    elif active_tab == nav_options[1]:
        if df_trend is None:
            st.info("Selecione um arquivo `*_trend_analysis.parquet` na barra lateral ou execute o pipeline na aba anterior.")
        else:
            df_view = df_trend
            if "index_name" in df_trend.columns:
                avail_indices = sorted(df_trend["index_name"].dropna().unique().tolist())
                chosen_idx = st.selectbox("Índice Espectral", avail_indices, key="tab_overview_idx")
                df_view = df_trend[df_trend["index_name"] == chosen_idx]

            meta_cols = [c for c in df_view.columns if not c.startswith("d_")]

            col1, col2, col3, col4 = st.columns(4)
            sig_pos = int(((df_view["trend_m"] > 0) & (df_view["trend_pv"] < 0.05)).sum())
            sig_neg = int(((df_view["trend_m"] < 0) & (df_view["trend_pv"] < 0.05)).sum())
            col1.metric("Polígonos", len(df_view))
            col2.metric("Tendência Média (trend_m)", f"{df_view['trend_m'].mean():.4f}")
            col3.metric("Ganho Significativo (p < 0.05)", sig_pos)
            col4.metric("Perda Significativa (p < 0.05)", sig_neg)

            st.subheader("Filtros da Tabela")
            f1, f2, f3 = st.columns(3)
            max_pv = f1.slider("p-valor máximo (trend_pv)", 0.0, 1.0, 1.0, 0.01)
            min_r2 = f2.slider("R² mínimo", 0.0, 1.0, 0.0, 0.05)
            trend_dir = f3.selectbox("Direção", ["Todas", "Positiva (trend_m > 0)", "Negativa (trend_m < 0)"])

            filtered = df_view[(df_view["trend_pv"] <= max_pv) & (df_view["r2"] >= min_r2)]
            if trend_dir.startswith("Positiva"):
                filtered = filtered[filtered["trend_m"] > 0]
            elif trend_dir.startswith("Negativa"):
                filtered = filtered[filtered["trend_m"] < 0]

            c_left, c_right = st.columns(2)
            with c_left:
                fig_hist = px.histogram(
                    filtered, x="trend_m", nbins=40, title="Distribuição de trend_m (Slope OLS)"
                )
                st.plotly_chart(fig_hist, use_container_width=True)
            with c_right:
                fig_scatter = px.scatter(
                    filtered,
                    x="trend_m",
                    y="trend_pv",
                    color="r2",
                    hover_data=["id_pol", "trend_m", "diff_trend", "r2"],
                    title="Significância (trend_pv) vs. Slope (trend_m)",
                )
                fig_scatter.add_hline(y=0.05, line_dash="dash", line_color="red")
                st.plotly_chart(fig_scatter, use_container_width=True)

            st.subheader(f"Tabela de Resultados ({len(filtered)} registros)")
            st.dataframe(filtered[meta_cols], use_container_width=True, height=400)
            st.download_button(
                "Baixar tabela filtrada (CSV)",
                data=filtered[meta_cols].to_csv(index=False).encode("utf-8"),
                file_name="theropoda_trends_filtered.csv",
                mime="text/csv",
            )

    elif active_tab == nav_options[2]:
        if df_trend is None:
            st.info("Selecione um arquivo `*_trend_analysis.parquet` para visualizar séries temporais.")
        else:
            date_cols = [c for c in df_trend.columns if c.startswith("d_")]
            df_ts = df_trend
            active_idx = "NDVI"
            if "index_name" in df_trend.columns:
                avail_indices = sorted(df_trend["index_name"].dropna().unique().tolist())
                active_idx = st.selectbox("Índice Espectral", avail_indices, key="tab_ts_idx")
                df_ts = df_trend[df_trend["index_name"] == active_idx]

            poly_ids = df_ts["id_pol"].tolist()
            chosen_id = st.selectbox("Selecione o Polígono (id_pol)", poly_ids)

            row = df_ts[df_ts["id_pol"] == chosen_id].iloc[0]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("trend_m", f"{row['trend_m']:.5f}")
            m2.metric("trend_pv", f"{row['trend_pv']:.5f}")
            m3.metric("r2", f"{row['r2']:.4f}")
            m4.metric("diff_trend", f"{row['diff_trend']:.5f}")

            ts_dates = pd.to_datetime([c.replace("d_", "") for c in date_cols])
            ts_vals = row[date_cols].to_numpy(dtype=float)

            raw_df = pd.DataFrame()
            raw_val_col = f"{active_idx}_median"
            if has_db:
                tables = load_sqlite_tables(selected_db)
                obs_table = "observations" if "observations" in tables else ("restoration" if "restoration" in tables else None)
                if obs_table:
                    cols_info = load_sqlite_query(selected_db, f"PRAGMA table_info({obs_table})")
                    col_names = cols_info["name"].tolist()
                    standard_cols = {
                        "id", "image_id", "date", "satelite", "MGRS_TILE", "WRS_PATH", "WRS_ROW",
                        "AREA_HA", "Pixel_Count", "Total_Pixels", "Pixel_Size",
                    }
                    custom_id_cols = [
                        c for c in col_names if c not in standard_cols and not c.endswith("_median")
                    ]
                    default_id_col = custom_id_cols[0] if custom_id_cols else ("id_pol" if "id_pol" in col_names else col_names[0])
                    id_col = st.selectbox(
                        "Coluna de ID no SQLite",
                        options=col_names,
                        index=col_names.index(default_id_col),
                    )
                    raw_df = load_sqlite_query(
                        selected_db,
                        f"SELECT *, ((Pixel_Count * 1.0 / Total_Pixels) * 100) AS Pixel_used "
                        f"FROM {obs_table} WHERE {id_col} = ? ORDER BY date",
                        params=(chosen_id,),
                    )
                    if not raw_df.empty:
                        raw_df["date"] = pd.to_datetime(raw_df["date"])
                        if raw_val_col not in raw_df.columns:
                            median_cols = [c for c in raw_df.columns if c.endswith("_median")]
                            raw_val_col = median_cols[0] if median_cols else "NDVI_median"

            show_raw = st.checkbox("Sobrepor observações brutas (.db) no painel Observed", value=True, disabled=raw_df.empty)
            x_norm = np.arange(len(ts_vals)) / max(1, len(ts_vals))
            ols_line = row["intercept_m"] + row["trend_m"] * x_norm

            # Infer season_size from median date step (matches trend_analysis.py)
            diffs = np.diff(ts_dates).astype("timedelta64[D]").astype(int)
            window_days = int(np.median(diffs)) if len(diffs) > 0 and np.median(diffs) > 0 else 15
            season_size = max(3, round(365 / window_days))
            seasonal_smooth = season_size + 2 if (season_size + 2) % 2 == 1 else season_size + 3

            if len(ts_vals) >= 2 * season_size and not np.isnan(ts_vals).any():
                stl_res = STL(
                    ts_vals,
                    period=season_size,
                    seasonal=seasonal_smooth,
                    trend=(2 * season_size) + 1,
                    robust=True,
                ).fit()

                fig = make_subplots(
                    rows=3,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.06,
                    subplot_titles=(f"Observed ({active_idx} Gap-Filled + Trend STL + OLS)", "Season", "Resid"),
                )
                if show_raw and not raw_df.empty and raw_val_col in raw_df.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=raw_df["date"],
                            y=raw_df[raw_val_col],
                            mode="markers",
                            name="Observações Brutas (.db)",
                            marker=dict(size=4, opacity=0.45, color="#7f7f7f"),
                        ),
                        row=1,
                        col=1,
                    )
                fig.add_trace(
                    go.Scatter(x=ts_dates, y=ts_vals, mode="lines", name="Observed", line=dict(color="#1f77b4")),
                    row=1,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=ts_dates,
                        y=stl_res.trend,
                        mode="lines",
                        name="Trend (STL)",
                        line=dict(color="#ff7f0e", width=2),
                    ),
                    row=1,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=ts_dates,
                        y=ols_line,
                        mode="lines",
                        name="Tendência OLS",
                        line=dict(dash="dash", width=2, color="crimson"),
                    ),
                    row=1,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(x=ts_dates, y=stl_res.seasonal, mode="lines", name="Season", line=dict(color="#1f77b4")),
                    row=2,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=ts_dates,
                        y=stl_res.resid,
                        mode="markers",
                        name="Resid",
                        marker=dict(size=5, color="#1f77b4"),
                    ),
                    row=3,
                    col=1,
                )
                fig.add_hline(y=0, line_dash="solid", line_color="black", line_width=1, row=3, col=1)

                fig.update_yaxes(title_text=active_idx, row=1, col=1)
                fig.update_yaxes(title_text="Season", row=2, col=1)
                fig.update_yaxes(title_text="Resid", row=3, col=1)
                fig.update_xaxes(title_text="Data", row=3, col=1)
                fig.update_layout(
                    title=f"Decomposição STL — Polígono {chosen_id} (period={season_size}, window≈{window_days}d)",
                    height=700,
                    showlegend=True,
                )
            else:
                st.warning(
                    f"Série muito curta ou com valores ausentes para decomposição STL (n={len(ts_vals)}, mínimo={2 * season_size})."
                )
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(x=ts_dates, y=ts_vals, mode="lines+markers", name="Série Padronizada + Gap-Filled")
                )
                fig.add_trace(
                    go.Scatter(
                        x=ts_dates,
                        y=ols_line,
                        mode="lines",
                        name="Tendência OLS",
                        line=dict(dash="dash", width=3, color="crimson"),
                    )
                )
                fig.update_layout(title=f"Série Temporal NDVI — Polígono {chosen_id}", height=500)

            st.plotly_chart(fig, use_container_width=True)

    elif active_tab == nav_options[3]:
        if not has_db:
            st.info("Selecione um arquivo `.db` na barra lateral para explorar o banco SQLite.")
        else:
            tables = load_sqlite_tables(selected_db)
            st.write(f"Tabelas encontradas em `{os.path.basename(selected_db)}`: `{tables}`")
            if tables:
                table_name = st.selectbox("Tabela", tables)
                limit = st.number_input("Limite de linhas", min_value=10, max_value=50000, value=500, step=100)
                custom_where = st.text_input("Cláusula WHERE opcional (ex.: Pixel_Count > 10)", value="")
                query = f"SELECT * FROM {table_name}"
                if custom_where.strip():
                    query += f" WHERE {custom_where.strip()}"
                query += f" LIMIT {int(limit)}"
                try:
                    db_df = load_sqlite_query(selected_db, query)
                    st.dataframe(db_df, use_container_width=True, height=450)
                    st.download_button(
                        "Exportar consulta (CSV)",
                        data=db_df.to_csv(index=False).encode("utf-8"),
                        file_name=f"{table_name}_query.csv",
                        mime="text/csv",
                    )
                except Exception as exc:
                    st.error(f"Erro na consulta SQL: {exc}")


if __name__ == "__main__":
    main()
