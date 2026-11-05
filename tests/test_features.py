"""Shared features match the notebook and reproduce the exported forecast (scope §8)."""

import ast
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

import aqi_forecasting
from aqi_forecasting.config import DATA_DIR, MODEL_DIR, N_HARMONICS
from aqi_forecasting.features import (
    add_regime_flags,
    build_features,
    fourier_terms,
    season_labels,
)


@pytest.fixture(scope="module")
def features(dashboard_daily: pd.DataFrame) -> pd.DataFrame:
    return build_features(dashboard_daily)


def test_season_labels_match_dashboard_column(dashboard_daily: pd.DataFrame) -> None:
    labels = season_labels(dashboard_daily.index)
    assert (labels == dashboard_daily["season"].astype(str).to_numpy()).all()


def test_regime_flags_match_dashboard_columns(dashboard_daily: pd.DataFrame) -> None:
    flags = add_regime_flags(dashboard_daily.drop(columns=["post_cams_49r1", "post_cams_50r1"]))
    for name in ("post_cams_49r1", "post_cams_50r1"):
        pd.testing.assert_series_equal(flags[name], dashboard_daily[name])


def test_fourier_terms_names_and_range() -> None:
    index = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    terms = fourier_terms(index, N_HARMONICS)
    assert list(terms) == ["sin_doy_1", "cos_doy_1", "sin_doy_2", "cos_doy_2"]
    assert all(np.abs(values).max() <= 1 for values in terms.values())


def test_features_cover_the_model_inputs(
    features: pd.DataFrame, preprocessing_config: dict
) -> None:
    assert set(preprocessing_config["feature_columns"]) <= set(features.columns)


def test_first_complete_row_is_the_train_start(
    features: pd.DataFrame, preprocessing_config: dict
) -> None:
    complete = features[preprocessing_config["feature_columns"]].dropna()
    assert complete.index[0] == pd.Timestamp(preprocessing_config["split_bounds"]["train"][0])


def test_features_are_causal(dashboard_daily: pd.DataFrame, features: pd.DataFrame) -> None:
    cutoff = pd.Timestamp("2025-06-30")
    truncated = build_features(dashboard_daily.loc[:cutoff])
    pd.testing.assert_series_equal(truncated.loc[cutoff], features.loc[cutoff])


def test_feature_parity_reproduces_forecast_latest(
    dashboard_daily: pd.DataFrame, features: pd.DataFrame
) -> None:
    """The refit model on the last day's features reproduces forecast_latest.parquet."""
    params = json.loads((MODEL_DIR / "rf_tuned_final_params.json").read_text())
    model = joblib.load(MODEL_DIR / "rf_tuned_final.joblib")
    assert model.n_features_in_ == 27
    assert list(model.feature_names_in_) == params["features"]

    latest = features[params["features"]].iloc[[-1]]
    assert latest.index[0] == dashboard_daily.index[-1]
    assert not latest.isna().any(axis=None)

    forecast = pd.read_parquet(DATA_DIR / "forecast_latest.parquet")
    np.testing.assert_allclose(model.predict(latest)[0], forecast["aqi_pred"], atol=1e-6)
    expected_dates = latest.index[0] + pd.to_timedelta(forecast["horizon"], unit="D")
    assert (forecast["date"] == expected_dates).all()


def _top_level_imports(path: Path) -> set[str]:
    """Return the top-level module names imported by a Python file."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_shared_package_does_not_import_streamlit() -> None:
    for path in Path(aqi_forecasting.__file__).parent.rglob("*.py"):
        assert "streamlit" not in _top_level_imports(path), path
