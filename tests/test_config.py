"""Shared constants match the notebook (NB §3.2) and the exported artifacts."""

import math

import pandas as pd

from aqi_forecasting import config


def test_aqi_categories_match_notebook() -> None:
    assert config.AQI_LABELS == [
        "Good",
        "Moderate",
        "Unhealthy for Sensitive Groups",
        "Unhealthy",
        "Very Unhealthy",
        "Hazardous",
    ]
    assert config.AQI_BINS == [0, 50, 100, 150, 200, 300, math.inf]
    assert config.AQI_COLORS == ["#00e400", "#ffff00", "#ff7e00", "#ff0000", "#8f3f97", "#7e0023"]


def test_every_model_input_has_a_display_label() -> None:
    catalogue = {*config.POLLUTANT_FEATURES, *config.WEATHER_FEATURES}
    assert {*config.POLLUTANT_COLS, *config.WEATHER_COLS} <= catalogue


def test_constants_match_preprocessing_config(preprocessing_config: dict) -> None:
    assert preprocessing_config["target"] == config.TARGET
    assert preprocessing_config["horizon"] == config.HORIZON
    assert preprocessing_config["target_columns"] == config.TARGET_COLS
    assert preprocessing_config["embargo_days"] == config.EMBARGO
    assert preprocessing_config["split_ratios"] == config.SPLIT_RATIOS
    assert preprocessing_config["cams_upgrades"] == config.CAMS_UPGRADES
    raw_inputs = config.POLLUTANT_COLS + config.WEATHER_COLS + config.MODEL_REGIME_FLAGS
    assert set(raw_inputs) <= set(preprocessing_config["feature_columns"])


def test_categories_and_seasons_match_dashboard_data(dashboard_daily: pd.DataFrame) -> None:
    assert list(dashboard_daily["aqi_category"].cat.categories) == config.AQI_LABELS
    is_wet = dashboard_daily.index.month.isin(config.WET_SEASON_MONTHS)
    expected = pd.Series(is_wet, index=dashboard_daily.index).map({True: "Wet", False: "Dry"})
    assert (dashboard_daily["season"].astype(str) == expected).all()


def test_repository_paths_exist() -> None:
    for path in (config.DATA_DIR, config.ARTIFACT_DIR, config.MODEL_DIR):
        assert path.is_dir(), path
