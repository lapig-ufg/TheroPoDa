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


def extract_ts(df, dt_windows):
    """Extract median NDVI time series over standardized temporal windows."""
    ts, dates = [], []

    for dt1, dt2 in dt_windows:
        df_dt = df.loc[(df["date"] >= dt1) & (df["date"] <= dt2)]
        ts.append(df_dt[df_dt["Pixel_used"] >= 70]["NDVI_median"].mean())
        dates.append((dt2 - relativedelta(days=2)).strftime("%Y-%m-%d"))

    return np.stack([np.stack([ts])]), dates


def gapfill(ts, dates, season_size):
    """Fill gaps in the time series using SeasConvFill."""
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


def run(input_file, id_pol, dt_windows, season_size, field_id, output_file):
    """Execute gap filling and trend analysis for a single polygon ID."""
    with sqlite3.connect(f"file:{input_file}?mode=ro", uri=True) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        table_name = "observations" if "observations" in tables else "restoration"
        df_sql = (
            f"SELECT *, ((Pixel_Count * 1.0 / Total_Pixels) * 100) AS Pixel_used "
            f"FROM {table_name} WHERE {field_id} = ?"
        )
        df = pd.read_sql_query(df_sql, con=con, params=[id_pol])

    df.loc[:, "date"] = pd.to_datetime(df["date"], errors="coerce")

    ts, dates = extract_ts(df, dt_windows)
    ts, dates = gapfill(ts, dates, season_size)

    seasonal_smooth = season_size + 2 if (season_size + 2) % 2 == 1 else season_size + 3
    trend, trend_cols = sm_trend(ts, season_size, seasonal_smooth)

    try:
        numeric_id = int(id_pol)
        ts_type = np.array([[[numeric_id, 1]]])
    except (TypeError, ValueError):
        ts_type = np.array([[[0, 1]]])

    columns = ["id_pol", "type"] + trend_cols + [f"d_{d}" for d in dates]
    result = pd.DataFrame(np.concatenate([ts_type, trend, ts], axis=-1)[0, :, :], columns=columns)
    result = result.round(8)
    result.loc[:, "id_pol"] = id_pol if not isinstance(id_pol, (int, np.integer)) else int(id_pol)

    result.to_parquet(output_file, partition_cols=["id_pol"])
    ttprint(f"Polygon {id_pol} saved in {output_file}")
    return id_pol
