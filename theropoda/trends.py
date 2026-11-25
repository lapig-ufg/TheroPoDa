import sqlite3
import numpy as np
import pandas as pd
import statsmodels.api as sm

from skmap.misc import ttprint
from dateutil.relativedelta import relativedelta
from skmap.io.process import SeasConvFill
from statsmodels.tsa.seasonal import STL
from loguru import logger

logger.add("trend_log_do_.log", rotation="500 MB")


def extract_ts(df, dt_windows, value_col: str = "NDVI_median"):
    """Extract median spectral index time series over standardized temporal windows."""
    ts, dates = [], []

    for dt1, dt2 in dt_windows:
        df_dt = df.loc[(df["date"] >= dt1) & (df["date"] <= dt2)]
        ts.append(df_dt[df_dt["Pixel_used"] >= 70][value_col].mean())
        dates.append((dt2 - relativedelta(days=2)).strftime("%Y-%m-%d"))

    return np.stack([np.stack([ts])]), dates


def gapfill(ts, dates, season_size):
    """Fill internal gaps in the time series using SeasConvFill."""
    seasconv = SeasConvFill(season_size=season_size)
    ts = seasconv._gapfill(ts)
    trim = 10 if ts.shape[2] > 10 else 0
    return ts[:, :, trim:], dates[trim:]


def sm_trend(ts, season_size, seasonal_smooth):
    """Apply STL seasonal decomposition and OLS linear trend regression."""
    sm_cols = [
        "intercept_m",
        "intercept_sd",
        "intercept_tv",
        "intercept_pv",
        "trend_m",
        "trend_sd",
        "trend_tv",
        "trend_pv",
        "r2",
        "diff_trend",
    ]

    result = []
    for i in range(ts.shape[1]):
        res = STL(
            ts[0, i, :],
            period=season_size,
            seasonal=seasonal_smooth,
            trend=(2 * season_size) + 1,
            robust=True,
        ).fit()
        y = res.trend
        diff_trend = res.trend[-1] - res.trend[0]

        y_size = y.shape[0]
        X = np.arange(y_size) / y_size
        X = sm.add_constant(X)
        results = sm.OLS(y, X).fit()

        result_stack = np.stack(
            [results.params, results.bse, results.tvalues, results.pvalues],
            axis=1,
        )
        result.append(
            np.concatenate(
                [
                    result_stack[0, :],
                    result_stack[1, :],
                    np.stack([results.rsquared, diff_trend]),
                ]
            )
        )

    return np.stack([np.stack(result)]), sm_cols


def run(input_file, id_pol, dt_windows, season_size, field_id, output_file, value_col: str = "NDVI_median", index_name: str = None):
    """Execute gap filling and trend analysis strictly over the polygon's observed date span."""
    with sqlite3.connect(f"file:{input_file}?mode=ro", uri=True) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        table_name = "observations" if "observations" in tables else "restoration"
        df_sql = (
            f"SELECT *, ((Pixel_Count * 1.0 / Total_Pixels) * 100) AS Pixel_used "
            f"FROM {table_name} WHERE {field_id} = ?"
        )
        df = pd.read_sql_query(df_sql, con=con, params=[id_pol])

    df.loc[:, "date"] = pd.to_datetime(df["date"], errors="coerce")

    ts_raw, dates_raw = extract_ts(df, dt_windows, value_col=value_col)
    full_trim = 10 if ts_raw.shape[2] > 10 else 0
    full_dates = dates_raw[full_trim:]

    valid_mask = ~np.isnan(ts_raw[0, 0, :])
    if not valid_mask.any():
        logger.warning(f"Polygon {id_pol} ({index_name or value_col}) has no valid observations (>=70% pixels). Skipping.")
        return None

    first_idx = int(np.argmax(valid_mask))
    last_idx = int(len(valid_mask) - 1 - np.argmax(valid_mask[::-1]))
    sub_ts = ts_raw[:, :, first_idx : last_idx + 1]
    sub_dates = dates_raw[first_idx : last_idx + 1]

    # Need at least 2 seasonal cycles (24 months for 15-day windows) after SeasConvFill trim
    sub_filled, sub_dates_filled = gapfill(sub_ts, sub_dates, season_size)
    if sub_filled.shape[2] < 2 * season_size:
        logger.warning(
            f"Polygon {id_pol} ({index_name or value_col}) span too short for STL "
            f"({sub_filled.shape[2]} < {2 * season_size} steps). Skipping."
        )
        return None

    seasonal_smooth = season_size + 2 if (season_size + 2) % 2 == 1 else season_size + 3
    trend, trend_cols = sm_trend(sub_filled, season_size, seasonal_smooth)

    # Place filled sub-series back onto the global date grid without extrapolating outside [first_idx, last_idx]
    full_ts = np.full((1, 1, len(full_dates)), np.nan, dtype=float)
    date_to_pos = {d: pos for pos, d in enumerate(full_dates)}
    for local_i, d_str in enumerate(sub_dates_filled):
        if d_str in date_to_pos:
            full_ts[0, 0, date_to_pos[d_str]] = sub_filled[0, 0, local_i]

    try:
        numeric_id = int(id_pol)
        ts_type = np.array([[[numeric_id, 1]]])
    except (TypeError, ValueError):
        ts_type = np.array([[[0, 1]]])

    columns = ["id_pol", "type"] + trend_cols + [f"d_{d}" for d in full_dates]
    result = pd.DataFrame(np.concatenate([ts_type, trend, full_ts], axis=-1)[0, :, :], columns=columns)
    result = result.round(8)
    if isinstance(id_pol, (int, np.integer)):
        result["id_pol"] = int(id_pol)
    else:
        result["id_pol"] = result["id_pol"].astype(object)
        result.loc[:, "id_pol"] = str(id_pol)

    if index_name:
        result.insert(1, "index_name", index_name)
        result.to_parquet(output_file, partition_cols=["index_name", "id_pol"])
    else:
        result.to_parquet(output_file, partition_cols=["id_pol"])
    ttprint(f"Polygon {id_pol} ({index_name or value_col}) saved in {output_file}")
    return id_pol
