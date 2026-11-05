"""Forecast reliability on the held-out test split (scope §4.3, NB §7.3–7.4, §7.8).

Train and validation predictions are in-sample (NB §6.4 ``tune_and_refit``), so every figure
here uses ``split == "test"`` with imputed targets excluded.
"""

from dataclasses import dataclass

import pandas as pd

from aqi_forecasting.config import SMAPE_TARGET, TARGET
from aqi_forecasting.metrics import compute_metrics, naive_forecasts, to_long

MODEL = "rf_tuned"
BENCHMARKS = ("persistence", "climatology")


def test_rows(predictions: pd.DataFrame) -> pd.DataFrame:
    """Test-split predictions with observed (non-imputed) targets."""
    keep = (predictions["split"] == "test") & ~predictions["target_is_imputed"]
    return predictions.loc[keep].reset_index(drop=True)


def evaluation_long(predictions: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """rf_tuned and both naive benchmarks in long format, as in NB §7.3.

    Persistence repeats the AQI of the base date; climatology is the train + val mean AQI of
    the target date's calendar month.
    """
    aqi = daily[TARGET]
    model = test_rows(predictions)
    base_dates = pd.DatetimeIndex(sorted(model["base_date"].unique()), name="base_date")
    ref_dates = pd.DatetimeIndex(
        predictions.loc[predictions["split"].isin(["train", "val"]), "base_date"].unique()
    )
    part = pd.DataFrame({"aqi_t": aqi.reindex(base_dates).to_numpy()}, index=base_dates)
    reference = pd.DataFrame({"aqi_t": aqi.reindex(ref_dates).to_numpy()}, index=ref_dates)

    y_true = model.set_index(["base_date", "horizon"])["y_true"]
    frames = [model[["base_date", "horizon", "y_true", "y_pred"]].assign(model=MODEL)]
    for name, wide in naive_forecasts(part, reference).items():
        long = to_long(wide, "y_pred").to_frame().join(y_true).reset_index()
        frames.append(long.assign(model=name))
    return pd.concat(frames, ignore_index=True)


def per_horizon(long: pd.DataFrame) -> pd.DataFrame:
    """Metrics per model and horizon (NB §7.4 per-horizon table)."""
    return compute_metrics(long)


def summary(per_h: pd.DataFrame) -> pd.DataFrame:
    """Mean over the seven horizons per model (NB §7.4 headline table), model first."""
    table = per_h.groupby(level="model").mean()
    return table.loc[[MODEL, *BENCHMARKS]]


@dataclass(frozen=True)
class Scorecard:
    """Success criteria of NB §2.4 as assessed in NB §7.8 (test split)."""

    b3_met: bool  # category accuracy above the best benchmark
    model_accuracy: float
    best_benchmark_accuracy: float
    d4_met: bool  # RMSE and MAE below every benchmark
    model_rmse: float
    best_benchmark_rmse: float
    model_mae: float
    best_benchmark_mae: float
    d5_met: bool  # mean sMAPE at or below the target
    model_smape: float
    smape_target: float
    day1_smape: float


def scorecard(per_h: pd.DataFrame) -> Scorecard:
    table = summary(per_h)
    model, bench = table.loc[MODEL], table.loc[list(BENCHMARKS)]
    return Scorecard(
        b3_met=bool(model["Category accuracy (%)"] > bench["Category accuracy (%)"].max()),
        model_accuracy=float(model["Category accuracy (%)"]),
        best_benchmark_accuracy=float(bench["Category accuracy (%)"].max()),
        d4_met=bool(model["RMSE"] < bench["RMSE"].min() and model["MAE"] < bench["MAE"].min()),
        model_rmse=float(model["RMSE"]),
        best_benchmark_rmse=float(bench["RMSE"].min()),
        model_mae=float(model["MAE"]),
        best_benchmark_mae=float(bench["MAE"].min()),
        d5_met=bool(model["sMAPE (%)"] <= SMAPE_TARGET),
        model_smape=float(model["sMAPE (%)"]),
        smape_target=SMAPE_TARGET,
        day1_smape=float(per_h.loc[(MODEL, 1), "sMAPE (%)"]),
    )


def regime_table(metrics: pd.DataFrame) -> pd.DataFrame:
    """Test RMSE and n per horizon before and after the CAMS 50r1 upgrade (metrics parquet)."""
    test = metrics.xs("test", level="split")
    wide = test["RMSE"].unstack("post_cams_50r1").rename(columns={False: "before", True: "after"})
    counts = (
        test["n"].unstack("post_cams_50r1").rename(columns={False: "n_before", True: "n_after"})
    )
    return wide.join(counts).reset_index()


def actual_vs_predicted(predictions: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Observed and predicted AQI by target date for one horizon (test split)."""
    rows = test_rows(predictions)
    rows = rows.loc[rows["horizon"] == horizon, ["target_date", "y_true", "y_pred"]]
    return rows.sort_values("target_date").reset_index(drop=True)
