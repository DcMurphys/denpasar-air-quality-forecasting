"""Smoke test: the shared package is installed and importable."""

import aqi_forecasting


def test_package_is_importable() -> None:
    assert aqi_forecasting.__version__ == "0.1.0"
