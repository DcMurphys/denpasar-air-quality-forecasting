"""Key factors reproduce NB §4.5.4 (Spearman) and NB §7.7 (permutation importance)."""

import pandas as pd
import pytest

from aqi_forecasting.config import ARTIFACT_DIR
from dashboard.models import drivers

# NB §4.5.4 insight: same-day / next-day Spearman ρ with the AQI.
EXPECTED_RHO = {
    "pm2_5_mean": (0.91, 0.89),
    "pm10_mean": (0.80, 0.79),
    "ozone_mean": (0.64, 0.60),
    "nitrogen_dioxide_mean": (0.43, 0.44),
    "sulphur_dioxide_mean": (0.34, 0.33),
    "carbon_monoxide_mean": (0.28, 0.28),
    "precipitation_hours": (-0.25, -0.27),
    "precipitation_sum": (-0.18, -0.20),
    "shortwave_radiation_sum": (0.15, 0.15),
}


@pytest.fixture(scope="module")
def ranking(dashboard_daily: pd.DataFrame) -> pd.DataFrame:
    return drivers.spearman_ranking(dashboard_daily)


@pytest.fixture(scope="module")
def importance() -> pd.DataFrame:
    return pd.read_csv(ARTIFACT_DIR / "feature_importance_rf_tuned.csv", index_col=0)


def test_spearman_matches_notebook(ranking: pd.DataFrame) -> None:
    rho = ranking.set_index("variable")[[drivers.SAME_DAY, drivers.NEXT_DAY]].round(2)
    for variable, expected in EXPECTED_RHO.items():
        assert tuple(rho.loc[variable]) == expected, variable
    assert len(ranking) == 12
    assert ranking.groupby("group").size().to_dict() == {"pollutant": 7, "weather": 5}


def test_importance_ranking(importance: pd.DataFrame) -> None:
    top = drivers.importance_ranking(importance)
    assert top["feature"].head(3).tolist() == ["pm2_5_mean", "pm10_mean", "aqi_roll30_std"]
    assert len(top) == 10
    assert (top["importance"] > 0).all()  # no-contribution features are never "important"
    assert drivers.n_without_contribution(importance) == 6


def test_findings(
    dashboard_daily: pd.DataFrame, ranking: pd.DataFrame, importance: pd.DataFrame
) -> None:
    f = drivers.findings(dashboard_daily, ranking, importance)
    assert round(f.wind_no2, 2) == -0.56 and round(f.wind_co, 2) == -0.41  # NB §4.5.4
    assert round(f.persistence, 2) == 0.76
    assert f.top_features == ("pm2_5_mean", "pm10_mean", "aqi_roll30_std")
    assert drivers.findings(dashboard_daily, ranking, None).top_features is None
