"""Load the notebook artifacts and validate them against the data contracts (scope §5).

Every loader raises ``ArtifactError`` when a file is missing, unreadable, or violates its
contract. The error carries a language-neutral ``kind`` code; views translate it.
Non-blocking checks (``data_version``, WHO flag) return booleans so that controllers can show a
warning instead of stopping the app.
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aqi_forecasting.config import (
    AQI_BINS,
    AQI_LABELS,
    ARTIFACT_DIR,
    CAMS_UPGRADES,
    CITY,
    DATA_DIR,
    HORIZON,
    MODEL_DIR,
    POLLUTANT_FEATURES,
    TARGET,
    WEATHER_FEATURES,
    WHO_PM25_24H_GUIDELINE,
)
from aqi_forecasting.features import season_labels

DASHBOARD_DAILY_PATH = DATA_DIR / "dashboard_daily.parquet"
FORECAST_PATH = DATA_DIR / "forecast_latest.parquet"
PREDICTIONS_PATH = DATA_DIR / "predictions_rf_tuned.parquet"
METRICS_PATH = DATA_DIR / "metrics_rf_tuned.parquet"
PREPROCESSING_CONFIG_PATH = ARTIFACT_DIR / "preprocessing_config.json"
MODEL_PARAMS_PATH = MODEL_DIR / "rf_tuned_final_params.json"
FEATURE_IMPORTANCE_PATH = ARTIFACT_DIR / "feature_importance_rf_tuned.csv"

N_FEATURES = 27
MODEL_NAME = "rf_tuned"
SPLITS = {"train", "val", "test", "embargo"}
# Columns added by the notebook after `data_version` was hashed (NB §5.1 add_dashboard_columns).
DASHBOARD_HELPER_COLUMNS = [
    "post_cams_49r1",
    "post_cams_50r1",
    "year",
    "month",
    "season",
    "aqi_category",
]

_DTYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
    "float": pd.api.types.is_float_dtype,
    "int": pd.api.types.is_integer_dtype,
    "bool": pd.api.types.is_bool_dtype,
    "datetime": pd.api.types.is_datetime64_any_dtype,
    "category": lambda dtype: isinstance(dtype, pd.CategoricalDtype),
    "text": lambda dtype: (
        pd.api.types.is_object_dtype(dtype) or pd.api.types.is_string_dtype(dtype)
    ),
}

DASHBOARD_DAILY_COLUMNS: dict[str, str] = {
    "city": "text",
    TARGET: "float",
    **dict.fromkeys(POLLUTANT_FEATURES, "float"),
    **dict.fromkeys(WEATHER_FEATURES, "float"),
    "exceeds_who_pm25": "bool",
    "is_imputed": "bool",
    "post_cams_49r1": "int",
    "post_cams_50r1": "int",
    "year": "int",
    "month": "int",
    "season": "category",
    "aqi_category": "category",
}
FORECAST_COLUMNS = {
    "date": "datetime",
    "horizon": "int",
    "aqi_pred": "float",
    "aqi_low": "float",
    "aqi_high": "float",
    "category": "category",
}
PREDICTION_COLUMNS = {
    "base_date": "datetime",
    "horizon": "int",
    "target_date": "datetime",
    "y_true": "float",
    "y_pred": "float",
    "residual": "float",
    "split": "category",
    "target_is_imputed": "bool",
    "post_cams_50r1": "bool",
    "model": "text",
}
METRIC_COLUMNS = ["n", "RMSE", "MAE", "sMAPE (%)", "Category accuracy (%)"]
METRIC_INDEX = ["split", "horizon", "post_cams_50r1"]
PREPROCESSING_KEYS = [
    "target",
    "horizon",
    "target_columns",
    "embargo_days",
    "feature_columns",
    "split_ratios",
    "split_bounds",
    "cams_upgrades",
    "data_version",
]


class ArtifactError(Exception):
    """An artifact is missing, unreadable, or violates its data contract.

    ``kind`` is one of ``"missing"``, ``"unreadable"``, or ``"invalid"`` and is used as a
    translation key; ``detail`` is an English message for the log.
    """

    def __init__(self, artifact: str, kind: str, path: Path, detail: str = "") -> None:
        self.artifact, self.kind, self.path, self.detail = artifact, kind, Path(path), detail
        super().__init__(f"{artifact} ({kind}) at {path}: {detail}".rstrip(": "))


# ===== Reading =====
def _read(artifact: str, path: Path, reader: Callable[[Path], Any]) -> Any:
    """Read a file, mapping I/O and parse failures to ``ArtifactError``."""
    path = Path(path)
    if not path.is_file():
        raise ArtifactError(artifact, "missing", path)
    try:
        return reader(path)
    except Exception as exc:  # any parse failure means the file cannot be used
        raise ArtifactError(artifact, "unreadable", path, f"{type(exc).__name__}: {exc}") from exc


def _require(condition: bool, artifact: str, path: Path, detail: str) -> None:
    if not condition:
        raise ArtifactError(artifact, "invalid", path, detail)


def _check_columns(df: pd.DataFrame, spec: dict[str, str], artifact: str, path: Path) -> None:
    missing = [col for col in spec if col not in df.columns]
    _require(not missing, artifact, path, f"missing columns {missing}")
    wrong = [col for col, kind in spec.items() if not _DTYPE_CHECKS[kind](df[col].dtype)]
    _require(not wrong, artifact, path, f"unexpected dtypes for {wrong}")


# ===== Loaders =====
def load_preprocessing_config(path: Path = PREPROCESSING_CONFIG_PATH) -> dict:
    """Load ``preprocessing_config.json`` (scope §5.5)."""
    name = "preprocessing_config"
    config = _read(name, path, lambda p: json.loads(p.read_text()))
    _require(isinstance(config, dict), name, path, "top level is not an object")
    missing = [key for key in PREPROCESSING_KEYS if key not in config]
    _require(not missing, name, path, f"missing keys {missing}")
    _require(config["horizon"] == HORIZON, name, path, f"horizon is {config['horizon']}")
    _require(
        config["cams_upgrades"] == CAMS_UPGRADES,
        name,
        path,
        f"CAMS upgrade dates are {config['cams_upgrades']}",
    )
    _require(
        len(config["feature_columns"]) == N_FEATURES,
        name,
        path,
        f"{len(config['feature_columns'])} feature columns, expected {N_FEATURES}",
    )
    expected_targets = [f"aqi_t+{h}" for h in range(1, HORIZON + 1)]
    _require(config["target_columns"] == expected_targets, name, path, "target columns differ")
    _require(
        {"train", "val", "test"} <= set(config["split_bounds"]),
        name,
        path,
        "split bounds incomplete",
    )
    return config


def load_dashboard_daily(path: Path = DASHBOARD_DAILY_PATH) -> pd.DataFrame:
    """Load ``dashboard_daily.parquet`` and validate it (scope §5.1)."""
    name = "dashboard_daily"
    df = _read(name, path, pd.read_parquet)
    _check_columns(df, DASHBOARD_DAILY_COLUMNS, name, path)
    index = df.index
    _require(
        isinstance(index, pd.DatetimeIndex) and index.name == "date",
        name,
        path,
        "index is not a DatetimeIndex named 'date'",
    )
    _require(len(df) > 0, name, path, "no rows")
    _require(
        index.is_unique and index.is_monotonic_increasing,
        name,
        path,
        "dates are not unique and increasing",
    )
    expected_days = (index[-1] - index[0]).days + 1
    _require(
        len(index) == expected_days,
        name,
        path,
        f"{expected_days - len(index)} missing days in the daily index",
    )
    _require(set(df["city"].unique()) == {CITY}, name, path, f"city is not only {CITY}")
    aqi = df[TARGET]
    _require(
        aqi.notna().all() and (aqi > 0).all(), name, path, f"{TARGET} has nulls or values <= 0"
    )
    _require(
        list(df["aqi_category"].cat.categories) == AQI_LABELS,
        name,
        path,
        "aqi_category labels differ from the shared config",
    )
    _require(
        (df["season"].astype(str).to_numpy() == season_labels(index)).all(),
        name,
        path,
        "season is inconsistent with month",
    )
    return df


def load_forecast(path: Path = FORECAST_PATH, *, last_date: pd.Timestamp) -> pd.DataFrame:
    """Load ``forecast_latest.parquet`` issued from data up to ``last_date`` (scope §5.2)."""
    name = "forecast_latest"
    df = _read(name, path, pd.read_parquet)
    _check_columns(df, FORECAST_COLUMNS, name, path)
    _require(
        df["horizon"].tolist() == list(range(1, HORIZON + 1)), name, path, "horizons are not 1..7"
    )
    expected_dates = pd.Timestamp(last_date) + pd.to_timedelta(df["horizon"], unit="D")
    _require(
        (df["date"] == expected_dates).all(),
        name,
        path,
        "dates do not follow the last observed day",
    )
    ordered = (df["aqi_low"] <= df["aqi_pred"]) & (df["aqi_pred"] <= df["aqi_high"])
    _require(ordered.all(), name, path, "band is not aqi_low <= aqi_pred <= aqi_high")
    expected = pd.cut(df["aqi_pred"], bins=AQI_BINS, labels=AQI_LABELS, include_lowest=True)
    _require(
        (df["category"].astype(str) == expected.astype(str)).all(),
        name,
        path,
        "category does not match aqi_pred",
    )
    return df


def load_predictions(path: Path = PREDICTIONS_PATH, *, test_bounds: list[str]) -> pd.DataFrame:
    """Load ``predictions_rf_tuned.parquet`` (scope §5.3)."""
    name = "predictions"
    df = _read(name, path, pd.read_parquet)
    _check_columns(df, PREDICTION_COLUMNS, name, path)
    _require(set(df["model"].unique()) == {MODEL_NAME}, name, path, f"model is not {MODEL_NAME}")
    _require(set(df["split"].astype(str).unique()) <= SPLITS, name, path, "unknown split labels")
    target_dates = df["base_date"] + pd.to_timedelta(df["horizon"], unit="D")
    _require(
        (df["target_date"] == target_dates).all(), name, path, "target_date != base_date + horizon"
    )
    _require(
        np.allclose(df["residual"], df["y_true"] - df["y_pred"]),
        name,
        path,
        "residual != y_true - y_pred",
    )
    test_dates = df.loc[df["split"] == "test", "base_date"]
    start, end = (pd.Timestamp(day) for day in test_bounds)
    _require(
        len(test_dates) > 0 and test_dates.between(start, end).all(),
        name,
        path,
        "test base dates outside the configured test bounds",
    )
    return df


def load_metrics(path: Path = METRICS_PATH) -> pd.DataFrame:
    """Load ``metrics_rf_tuned.parquet`` (scope §5.4)."""
    name = "metrics"
    df = _read(name, path, pd.read_parquet)
    _require(list(df.index.names) == METRIC_INDEX, name, path, f"index is not {METRIC_INDEX}")
    _require(list(df.columns) == METRIC_COLUMNS, name, path, f"columns are not {METRIC_COLUMNS}")
    _require((df["n"] > 0).all(), name, path, "n must be positive")
    return df


def load_model_params(path: Path = MODEL_PARAMS_PATH, *, preprocessing: dict) -> dict:
    """Load ``rf_tuned_final_params.json`` and match it to the preprocessing config (§5.6)."""
    name = "model_params"
    params = _read(name, path, lambda p: json.loads(p.read_text()))
    _require(
        isinstance(params, dict) and {"features", "targets", "params"} <= set(params),
        name,
        path,
        "missing keys",
    )
    _require(
        params["features"] == preprocessing["feature_columns"],
        name,
        path,
        "feature list or order differs from preprocessing_config.json",
    )
    _require(
        params["targets"] == preprocessing["target_columns"],
        name,
        path,
        "targets differ from preprocessing_config.json",
    )
    return params


def load_feature_importance(
    path: Path = FEATURE_IMPORTANCE_PATH, *, feature_columns: list[str]
) -> pd.DataFrame:
    """Load ``feature_importance_rf_tuned.csv`` indexed by feature name (scope §5.8)."""
    name = "feature_importance"
    df = _read(name, path, lambda p: pd.read_csv(p, index_col=0))
    _require(
        list(df.columns) == ["importance", "std"],
        name,
        path,
        "columns are not ['importance', 'std']",
    )
    _require(df.index.is_unique, name, path, "duplicate features")
    _require(
        set(df.index) == set(feature_columns),
        name,
        path,
        "features differ from the configured feature columns",
    )
    _require((df["std"] >= 0).all(), name, path, "negative standard deviation")
    return df


# ===== Non-blocking checks =====
def compute_data_version(df: pd.DataFrame) -> str:
    """Recompute the notebook's ``data_version`` hash (NB §5.3) from ``dashboard_daily``."""
    clean = df.drop(columns=DASHBOARD_HELPER_COLUMNS, errors="ignore")
    hashed = pd.util.hash_pandas_object(clean, index=True).to_numpy().tobytes()
    return hashlib.sha256(hashed).hexdigest()[:12]


def data_version_matches(df: pd.DataFrame, expected: str) -> bool:
    """True when ``dashboard_daily`` comes from the run recorded in the preprocessing config."""
    return compute_data_version(df) == expected


def who_flag_consistent(df: pd.DataFrame) -> bool:
    """True when ``exceeds_who_pm25`` equals ``pm2_5_mean > 15`` on every row (decision Q6)."""
    return bool((df["exceeds_who_pm25"] == (df["pm2_5_mean"] > WHO_PM25_24H_GUIDELINE)).all())
