"""Metric functions and naive benchmarks reproduce the notebook (NB §7.2–7.4)."""

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

from aqi_forecasting.metrics import (
    aqi_category_codes,
    category_accuracy,
    compute_metrics,
    mae,
    naive_forecasts,
    rmse,
    smape,
    to_long,
)

Y_TRUE = np.array([40.0, 55.0, 120.0, 90.0])
Y_PRED = np.array([45.0, 50.0, 95.0, 101.0])


def test_rmse_and_mae_hand_computed() -> None:
    assert rmse(Y_TRUE, Y_PRED) == pytest.approx(np.sqrt((25 + 25 + 625 + 121) / 4))
    assert mae(Y_TRUE, Y_PRED) == pytest.approx((5 + 5 + 25 + 11) / 4)


def test_rmse_and_mae_match_sklearn() -> None:
    rng = np.random.default_rng(126)
    y_true, y_pred = rng.uniform(15, 135, 500), rng.uniform(15, 135, 500)
    assert rmse(y_true, y_pred) == pytest.approx(root_mean_squared_error(y_true, y_pred))
    assert mae(y_true, y_pred) == pytest.approx(mean_absolute_error(y_true, y_pred))


def test_smape_hand_computed_and_zero_denominator() -> None:
    assert smape([100.0], [50.0]) == pytest.approx(200 * 50 / 150)
    assert smape([0.0, 10.0], [0.0, 10.0]) == 0.0


def test_category_codes_at_boundaries() -> None:
    values = [0, 50, 50.01, 100, 100.5, 150, 200, 300, 301]
    assert list(aqi_category_codes(values)) == [0, 0, 1, 1, 2, 2, 3, 4, 5]


def test_category_accuracy() -> None:
    # True (Good, Moderate, USG, Moderate) vs. pred (Good, Good, Moderate, USG) -> 1 of 4.
    assert category_accuracy(Y_TRUE, Y_PRED) == pytest.approx(25.0)


@pytest.fixture(scope="module")
def test_long(dashboard_daily: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    """Test-split predictions of rf_tuned plus both naive benchmarks, as in NB §7.3."""
    aqi = dashboard_daily["us_aqi_mean"]
    rf = predictions.loc[(predictions["split"] == "test") & ~predictions["target_is_imputed"]]
    base_dates = pd.DatetimeIndex(sorted(rf["base_date"].unique()), name="base_date")
    ref_dates = pd.DatetimeIndex(
        predictions.loc[predictions["split"].isin(["train", "val"]), "base_date"].unique()
    )
    part = pd.DataFrame({"aqi_t": aqi.reindex(base_dates).to_numpy()}, index=base_dates)
    reference = pd.DataFrame({"aqi_t": aqi.reindex(ref_dates).to_numpy()}, index=ref_dates)

    y_true = rf.set_index(["base_date", "horizon"])["y_true"]
    frames = [rf[["base_date", "horizon", "y_true", "y_pred", "model"]]]
    for name, wide in naive_forecasts(part, reference).items():
        long = to_long(wide, "y_pred").to_frame().join(y_true).reset_index()
        frames.append(long.assign(model=name))
    return pd.concat(frames, ignore_index=True)


def test_summary_reproduces_notebook_7_4(test_long: pd.DataFrame) -> None:
    summary = compute_metrics(test_long).groupby("model").mean().round(2)
    expected = pd.DataFrame(
        {
            "RMSE": [11.83, 13.65, 16.41],
            "MAE": [8.37, 9.98, 11.21],
            "sMAPE (%)": [16.79, 19.83, 21.98],
            "Category accuracy (%)": [76.96, 65.37, 72.47],
        },
        index=pd.Index(["rf_tuned", "climatology", "persistence"], name="model"),
    )
    pd.testing.assert_frame_equal(summary.loc[expected.index], expected)


def test_per_horizon_reproduces_notebook_7_4(test_long: pd.DataFrame) -> None:
    per_horizon = compute_metrics(test_long).loc["rf_tuned"].round(2)
    assert per_horizon["RMSE"].tolist() == [7.43, 11.05, 12.51, 12.93, 12.96, 12.94, 13.02]
    assert per_horizon["sMAPE (%)"].tolist()[0] == 10.39
    assert per_horizon["Category accuracy (%)"].tolist() == [
        90.07,
        83.77,
        78.15,
        72.85,
        71.85,
        70.86,
        71.19,
    ]
