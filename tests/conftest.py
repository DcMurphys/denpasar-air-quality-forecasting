"""Shared fixtures: the real notebook artifacts, loaded read-only once per test session.

"Today" is pinned to 2026-11-04 for every test (see ``dashboard.controllers.data.today``),
five days after the last observed day, so date-relative views are deterministic.
"""

import json

import pandas as pd
import pytest

from aqi_forecasting.config import ARTIFACT_DIR, DATA_DIR


@pytest.fixture(scope="session")
def dashboard_daily() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "dashboard_daily.parquet")


@pytest.fixture(scope="session")
def predictions() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "predictions_rf_tuned.parquet")


@pytest.fixture(scope="session")
def preprocessing_config() -> dict:
    return json.loads((ARTIFACT_DIR / "preprocessing_config.json").read_text())


TEST_TODAY = "2026-11-04"


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AQI_TODAY", TEST_TODAY)
