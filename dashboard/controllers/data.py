"""Cached artifact loaders (scope §6 caching strategy).

Each loader is keyed by the file path and its modification time, so a re-export invalidates the
cache without a TTL. Failed loads raise ``ArtifactError`` and are not cached.

The directories can be redirected with the environment variables ``AQI_DATA_DIR`` and
``AQI_ARTIFACT_DIR`` (used by smoke tests to simulate missing artifacts), and "today" can be
pinned with ``AQI_TODAY`` (ISO date) so that tests do not depend on the calendar.
"""

import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from aqi_forecasting import config
from dashboard.models import artifacts
from dashboard.models.forecast import local_today


def _data_dir() -> Path:
    return Path(os.environ.get("AQI_DATA_DIR", config.DATA_DIR))


def _artifact_dir() -> Path:
    return Path(os.environ.get("AQI_ARTIFACT_DIR", config.ARTIFACT_DIR))


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.is_file() else 0.0


@st.cache_data(show_spinner=False)
def _dashboard_daily(path: str, mtime: float) -> pd.DataFrame:
    return artifacts.load_dashboard_daily(Path(path))


@st.cache_data(show_spinner=False)
def _preprocessing_config(path: str, mtime: float) -> dict:
    return artifacts.load_preprocessing_config(Path(path))


@st.cache_data(show_spinner=False)
def _forecast(path: str, mtime: float, last_date: pd.Timestamp) -> pd.DataFrame:
    return artifacts.load_forecast(Path(path), last_date=last_date)


@st.cache_data(show_spinner=False)
def _feature_importance(path: str, mtime: float, feature_columns: tuple[str, ...]) -> pd.DataFrame:
    return artifacts.load_feature_importance(Path(path), feature_columns=list(feature_columns))


@st.cache_data(show_spinner=False)
def _predictions(path: str, mtime: float, test_bounds: tuple[str, str]) -> pd.DataFrame:
    return artifacts.load_predictions(Path(path), test_bounds=list(test_bounds))


@st.cache_data(show_spinner=False)
def _metrics(path: str, mtime: float) -> pd.DataFrame:
    return artifacts.load_metrics(Path(path))


@st.cache_data(show_spinner=False)
def _model_params(path: str, mtime: float, preprocessing: dict) -> dict:
    return artifacts.load_model_params(Path(path), preprocessing=preprocessing)


def dashboard_daily() -> pd.DataFrame:
    path = _data_dir() / artifacts.DASHBOARD_DAILY_PATH.name
    return _dashboard_daily(str(path), _mtime(path))


def preprocessing_config() -> dict:
    path = _artifact_dir() / artifacts.PREPROCESSING_CONFIG_PATH.name
    return _preprocessing_config(str(path), _mtime(path))


def forecast(last_date: pd.Timestamp) -> pd.DataFrame:
    path = _data_dir() / artifacts.FORECAST_PATH.name
    return _forecast(str(path), _mtime(path), last_date)


def feature_importance(feature_columns: list[str]) -> pd.DataFrame:
    path = _artifact_dir() / artifacts.FEATURE_IMPORTANCE_PATH.name
    return _feature_importance(str(path), _mtime(path), tuple(feature_columns))


def today() -> date:
    """Today in Denpasar, or ``AQI_TODAY`` when set (tests)."""
    pinned = os.environ.get("AQI_TODAY")
    return date.fromisoformat(pinned) if pinned else local_today()


def predictions(test_bounds: list[str]) -> pd.DataFrame:
    path = _data_dir() / artifacts.PREDICTIONS_PATH.name
    return _predictions(str(path), _mtime(path), tuple(test_bounds))


def metrics() -> pd.DataFrame:
    path = _data_dir() / artifacts.METRICS_PATH.name
    return _metrics(str(path), _mtime(path))


def model_params(preprocessing: dict) -> dict:
    path = _artifact_dir() / "trained_models" / artifacts.MODEL_PARAMS_PATH.name
    return _model_params(str(path), _mtime(path), preprocessing)
