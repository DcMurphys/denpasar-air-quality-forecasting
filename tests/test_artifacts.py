"""Artifact loaders accept the real artifacts and reject corrupted copies (scope §5, §8).

Corrupted copies are written to pytest's temporary directory; the real artifacts are never
modified.
"""

import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from dashboard.models import artifacts as art


# ===== Real artifacts =====
@pytest.fixture(scope="module")
def config() -> dict:
    return art.load_preprocessing_config()


@pytest.fixture(scope="module")
def daily() -> pd.DataFrame:
    return art.load_dashboard_daily()


@pytest.fixture(scope="module")
def forecast(daily: pd.DataFrame) -> pd.DataFrame:
    return art.load_forecast(last_date=daily.index[-1])


@pytest.fixture(scope="module")
def predictions(config: dict) -> pd.DataFrame:
    return art.load_predictions(test_bounds=config["split_bounds"]["test"])


def test_real_artifacts_load(
    config: dict, daily: pd.DataFrame, forecast: pd.DataFrame, predictions: pd.DataFrame
) -> None:
    assert daily.shape == (1548, 39)
    assert len(forecast) == 7
    assert len(predictions) == 10584
    assert art.load_metrics().shape == (28, 5)
    assert len(art.load_model_params(preprocessing=config)["features"]) == 27
    assert len(art.load_feature_importance(feature_columns=config["feature_columns"])) == 27


def test_data_version_and_who_flag(config: dict, daily: pd.DataFrame) -> None:
    assert art.compute_data_version(daily) == "b818fb605cff"
    assert art.data_version_matches(daily, config["data_version"])
    assert art.who_flag_consistent(daily)


def test_forecast_band_is_derived_from_test_residuals(
    forecast: pd.DataFrame, predictions: pd.DataFrame
) -> None:
    """P10/P90 band provenance (scope §5.2, decision Q4)."""
    test = predictions.loc[(predictions["split"] == "test") & ~predictions["target_is_imputed"]]
    quantiles = test.groupby("horizon")["residual"].quantile([0.1, 0.9]).unstack()
    by_horizon = forecast.set_index("horizon")
    pd.testing.assert_series_equal(
        by_horizon["aqi_pred"] + quantiles[0.1], by_horizon["aqi_low"], check_names=False
    )
    pd.testing.assert_series_equal(
        by_horizon["aqi_pred"] + quantiles[0.9], by_horizon["aqi_high"], check_names=False
    )


def test_non_blocking_checks_detect_changes(daily: pd.DataFrame) -> None:
    changed = daily.copy()
    changed.iloc[0, changed.columns.get_loc("pm2_5_mean")] += 1.0
    assert not art.data_version_matches(changed, "b818fb605cff")
    changed["exceeds_who_pm25"] = ~changed["exceeds_who_pm25"]
    assert not art.who_flag_consistent(changed)


# ===== Missing and unreadable files =====
def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(art.ArtifactError) as err:
        art.load_dashboard_daily(tmp_path / "absent.parquet")
    assert err.value.kind == "missing"


def test_unreadable_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.parquet"
    path.write_bytes(b"not a parquet file")
    with pytest.raises(art.ArtifactError) as err:
        art.load_dashboard_daily(path)
    assert err.value.kind == "unreadable"


# ===== Corrupted copies =====
def _shift_category(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.loc[0, "category"] = "Good"
    return df


DAILY_CORRUPTIONS: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "missing column": lambda d: d.drop(columns=["pm2_5_mean"]),
    "wrong dtype": lambda d: d.assign(us_aqi_mean=d["us_aqi_mean"].astype(str)),
    "gap in index": lambda d: d.drop(index=d.index[100]),
    "other city": lambda d: d.assign(city="Jakarta"),
    "non-positive aqi": lambda d: d.assign(us_aqi_mean=d["us_aqi_mean"].clip(upper=0.0)),
    "season flipped": lambda d: d.assign(
        season=d["season"].map({"Dry": "Wet", "Wet": "Dry"}).astype("category")
    ),
}


@pytest.mark.parametrize("corruption", DAILY_CORRUPTIONS, ids=list(DAILY_CORRUPTIONS))
def test_dashboard_daily_rejects(daily: pd.DataFrame, tmp_path: Path, corruption: str) -> None:
    path = tmp_path / "dashboard_daily.parquet"
    DAILY_CORRUPTIONS[corruption](daily).to_parquet(path)
    with pytest.raises(art.ArtifactError) as err:
        art.load_dashboard_daily(path)
    assert err.value.kind == "invalid"


FORECAST_CORRUPTIONS: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "horizon order": lambda f: f.iloc[::-1].reset_index(drop=True),
    "band order": lambda f: f.assign(aqi_low=f["aqi_pred"] + 1),
    "category": _shift_category,
    "dates shifted": lambda f: f.assign(date=f["date"] + pd.to_timedelta(1, unit="D")),
}


@pytest.mark.parametrize("corruption", FORECAST_CORRUPTIONS, ids=list(FORECAST_CORRUPTIONS))
def test_forecast_rejects(
    daily: pd.DataFrame, forecast: pd.DataFrame, tmp_path: Path, corruption: str
) -> None:
    path = tmp_path / "forecast_latest.parquet"
    FORECAST_CORRUPTIONS[corruption](forecast).to_parquet(path)
    with pytest.raises(art.ArtifactError) as err:
        art.load_forecast(path, last_date=daily.index[-1])
    assert err.value.kind == "invalid"


PREDICTION_CORRUPTIONS: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "residual": lambda p: p.assign(residual=p["residual"] + 1),
    "model name": lambda p: p.assign(model="gb_tuned"),
    "target date": lambda p: p.assign(target_date=p["base_date"]),
}


@pytest.mark.parametrize("corruption", PREDICTION_CORRUPTIONS, ids=list(PREDICTION_CORRUPTIONS))
def test_predictions_reject(
    config: dict, predictions: pd.DataFrame, tmp_path: Path, corruption: str
) -> None:
    path = tmp_path / "predictions.parquet"
    PREDICTION_CORRUPTIONS[corruption](predictions).to_parquet(path)
    with pytest.raises(art.ArtifactError) as err:
        art.load_predictions(path, test_bounds=config["split_bounds"]["test"])
    assert err.value.kind == "invalid"


def test_predictions_reject_test_dates_outside_bounds(
    predictions: pd.DataFrame, tmp_path: Path
) -> None:
    path = tmp_path / "predictions.parquet"
    predictions.to_parquet(path)
    with pytest.raises(art.ArtifactError):
        art.load_predictions(path, test_bounds=["2026-01-01", "2026-10-23"])


def test_metrics_reject_missing_column(tmp_path: Path) -> None:
    path = tmp_path / "metrics.parquet"
    art.load_metrics().drop(columns=["MAE"]).to_parquet(path)
    with pytest.raises(art.ArtifactError):
        art.load_metrics(path)


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload))
    return path


def test_preprocessing_config_rejects(config: dict, tmp_path: Path) -> None:
    short = {**config, "feature_columns": config["feature_columns"][:-1]}
    with pytest.raises(art.ArtifactError):
        art.load_preprocessing_config(_write_json(tmp_path / "short.json", short))
    incomplete = {key: value for key, value in config.items() if key != "data_version"}
    with pytest.raises(art.ArtifactError):
        art.load_preprocessing_config(_write_json(tmp_path / "incomplete.json", incomplete))
    moved = {**config, "cams_upgrades": {**config["cams_upgrades"], "post_cams_50r1": "2026-06-01"}}
    with pytest.raises(art.ArtifactError, match="CAMS upgrade dates"):
        art.load_preprocessing_config(_write_json(tmp_path / "moved.json", moved))


def test_model_params_reject_wrong_feature_order(config: dict, tmp_path: Path) -> None:
    params = art.load_model_params(preprocessing=config)
    swapped = params["features"][:]
    swapped[0], swapped[1] = swapped[1], swapped[0]
    path = _write_json(tmp_path / "params.json", {**params, "features": swapped})
    with pytest.raises(art.ArtifactError):
        art.load_model_params(path, preprocessing=config)


def test_feature_importance_rejects_missing_feature(config: dict, tmp_path: Path) -> None:
    path = tmp_path / "importance.csv"
    art.load_feature_importance(feature_columns=config["feature_columns"]).iloc[1:].to_csv(path)
    with pytest.raises(art.ArtifactError):
        art.load_feature_importance(path, feature_columns=config["feature_columns"])
