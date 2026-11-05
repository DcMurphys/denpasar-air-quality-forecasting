"""Forecast metrics and naive benchmarks (NB §7.2–7.3).

RMSE and MAE are implemented with numpy so that the shared package depends only on numpy and
pandas; they match ``sklearn.metrics.root_mean_squared_error`` and ``mean_absolute_error``.
"""

from collections.abc import Callable

import numpy as np
import pandas as pd

from aqi_forecasting.config import AQI_BINS, HORIZON, TARGET_COLS


def rmse(y_true, y_pred) -> float:
    """Root mean squared error in AQI units."""
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true, y_pred) -> float:
    """Mean absolute error in AQI units."""
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    return float(np.mean(np.abs(y_true - y_pred)))


def smape(y_true, y_pred) -> float:
    """Symmetric mean absolute percentage error in percent (0 where both values are 0)."""
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    denom = np.abs(y_true) + np.abs(y_pred)
    ratio = np.divide(2 * np.abs(y_pred - y_true), denom, out=np.zeros_like(denom), where=denom > 0)
    return float(ratio.mean() * 100)


def aqi_category_codes(values) -> np.ndarray:
    """Map AQI values to integer US AQI category codes (0 = Good ... 5 = Hazardous)."""
    return pd.cut(np.asarray(values), bins=AQI_BINS, labels=False, include_lowest=True)


def category_accuracy(y_true, y_pred) -> float:
    """Percentage of forecasts that fall in the same US AQI category as the actual value."""
    return float((aqi_category_codes(y_true) == aqi_category_codes(y_pred)).mean() * 100)


METRIC_FUNCS: dict[str, Callable[..., float]] = {
    "RMSE": rmse,
    "MAE": mae,
    "sMAPE (%)": smape,
    "Category accuracy (%)": category_accuracy,
}


def compute_metrics(long: pd.DataFrame) -> pd.DataFrame:
    """Compute metrics per model and horizon, in original AQI units.

    ``long`` needs the columns ``model``, ``horizon``, ``y_true``, and ``y_pred``. The headline
    figure of NB §7.4 is the mean over horizons: ``compute_metrics(long).groupby("model").mean()``.
    """
    return long.groupby(["model", "horizon"]).apply(
        lambda g: pd.Series(
            {name: func(g["y_true"], g["y_pred"]) for name, func in METRIC_FUNCS.items()}
        ),
        include_groups=False,
    )


def to_long(frame: pd.DataFrame, name: str) -> pd.Series:
    """Reshape columns aqi_t+1 ... aqi_t+H into a long Series indexed by (base_date, horizon)."""
    return (
        frame[TARGET_COLS]
        .set_axis(range(1, HORIZON + 1), axis=1)
        .rename_axis(index="base_date", columns="horizon")
        .stack()
        .rename(name)
    )


def naive_forecasts(part: pd.DataFrame, reference: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build naive benchmarks: persistence and monthly climatology.

    Persistence repeats the AQI of day t for every horizon. Climatology uses the
    train + val mean AQI of the target date's calendar month. Both frames need a
    DatetimeIndex of base dates and an ``aqi_t`` column.
    """
    persistence = pd.DataFrame(
        np.repeat(part[["aqi_t"]].to_numpy(), HORIZON, axis=1),
        index=part.index,
        columns=TARGET_COLS,
    )
    monthly_mean = reference["aqi_t"].groupby(reference.index.month).mean()
    climatology = pd.DataFrame(index=part.index, columns=TARGET_COLS, dtype=float)
    for h, col in enumerate(TARGET_COLS, start=1):
        # Same result as NB `+ pd.Timedelta(days=h)`, which warns under numpy 2.5.
        target_months = (part.index + pd.to_timedelta(h, unit="D")).month
        climatology[col] = monthly_mean.reindex(target_months).to_numpy()

    return {"persistence": persistence, "climatology": climatology}
