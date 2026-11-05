"""About-page facts read from the artifacts (scope §4.4, NB §3.4, §8.1)."""

from datetime import date

import pandas as pd
import pytest

from aqi_forecasting.config import ARTIFACT_DIR
from dashboard.models import artifacts, metadata


@pytest.fixture(scope="module")
def params(preprocessing_config: dict) -> dict:
    return artifacts.load_model_params(
        ARTIFACT_DIR / "trained_models" / "rf_tuned_final_params.json",
        preprocessing=preprocessing_config,
    )


def test_data_facts(dashboard_daily: pd.DataFrame, preprocessing_config: dict) -> None:
    facts = metadata.data_facts(dashboard_daily, preprocessing_config)
    assert facts.n_days == 1548
    assert facts.start == date(2022, 8, 5)
    assert facts.end == date(2026, 10, 30)
    assert facts.data_version == "b818fb605cff"
    assert facts.cams_upgrades and all("post_cams_" not in v for v in facts.cams_upgrades)


def test_model_facts_match_the_refit(
    dashboard_daily: pd.DataFrame, preprocessing_config: dict, params: dict
) -> None:
    facts = metadata.model_facts(dashboard_daily, preprocessing_config, params)
    assert facts.n_features == artifacts.N_FEATURES == 27
    assert facts.horizon == 7
    assert (facts.refit_start, facts.refit_end) == (date(2022, 9, 3), date(2026, 10, 23))
    assert facts.refit_rows == 1512
    assert facts.n_estimators > 0 and facts.max_depth > 0 and facts.min_samples_leaf > 0


def test_aqi_scale_bounds() -> None:
    scale = metadata.aqi_scale()
    assert scale["lower"].tolist() == [0, 51, 101, 151, 201, 301]
    assert scale["upper"].iloc[:5].tolist() == [50, 100, 150, 200, 300]
    assert pd.isna(scale["upper"].iloc[-1])
    assert scale["label"].iloc[-1] == "Hazardous"
