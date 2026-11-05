"""Reliability figures reproduce NB §7.4 and §7.8 on the test split only (scope §4.3)."""

import pandas as pd
import pytest

from aqi_forecasting.config import DATA_DIR
from dashboard.models import performance as pf


@pytest.fixture(scope="module")
def per_h(predictions: pd.DataFrame, dashboard_daily: pd.DataFrame) -> pd.DataFrame:
    return pf.per_horizon(pf.evaluation_long(predictions, dashboard_daily))


def test_only_test_split_is_used(predictions: pd.DataFrame) -> None:
    rows = pf.test_rows(predictions)
    assert set(rows["split"].astype(str)) == {"test"}
    assert not rows["target_is_imputed"].any()


def test_summary_matches_notebook(per_h: pd.DataFrame) -> None:
    table = pf.summary(per_h).round(2)
    assert table.index.tolist() == ["rf_tuned", "persistence", "climatology"]
    assert table.loc["rf_tuned"].tolist() == [11.83, 8.37, 16.79, 76.96]
    assert table.loc["persistence"].tolist() == [16.41, 11.21, 21.98, 72.47]
    assert table.loc["climatology"].tolist() == [13.65, 9.98, 19.83, 65.37]


def test_scorecard_matches_notebook_7_8(per_h: pd.DataFrame) -> None:
    card = pf.scorecard(per_h)
    assert card.b3_met and card.d4_met and not card.d5_met
    assert round(card.day1_smape, 2) == 10.39
    assert round(card.best_benchmark_accuracy, 2) == 72.47


def test_regime_table() -> None:
    metrics = pd.read_parquet(DATA_DIR / "metrics_rf_tuned.parquet")
    regime = pf.regime_table(metrics).set_index("horizon").round(2)
    assert regime.loc[1, ["before", "after"]].tolist() == [10.33, 3.61]
    assert len(regime) == 7


def test_actual_vs_predicted(predictions: pd.DataFrame) -> None:
    frame = pf.actual_vs_predicted(predictions, 1)
    assert len(frame) == 302 and frame["target_date"].is_monotonic_increasing
