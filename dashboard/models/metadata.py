"""Facts for the About page (scope §4.4), read from artifacts rather than typed into text."""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from aqi_forecasting.config import AQI_CATEGORIES


@dataclass(frozen=True)
class DataFacts:
    start: date
    end: date
    n_days: int
    data_version: str
    cams_upgrades: dict[str, str]  # version (e.g. "49r1") -> ISO date


@dataclass(frozen=True)
class ModelFacts:
    n_features: int
    horizon: int
    refit_start: date
    refit_end: date
    refit_rows: int
    n_estimators: int
    max_depth: int
    min_samples_leaf: int


def data_facts(daily: pd.DataFrame, config: dict) -> DataFacts:
    return DataFacts(
        start=daily.index[0].date(),
        end=daily.index[-1].date(),
        n_days=len(daily),
        data_version=config["data_version"],
        cams_upgrades={k.removeprefix("post_cams_"): v for k, v in config["cams_upgrades"].items()},
    )


def model_facts(daily: pd.DataFrame, config: dict, params: dict) -> ModelFacts:
    """The final model is refit on every labelled day, train start to test end (NB §8.1)."""
    start = pd.Timestamp(config["split_bounds"]["train"][0])
    end = pd.Timestamp(config["split_bounds"]["test"][1])
    hyper = params["params"]
    return ModelFacts(
        n_features=len(params["features"]),
        horizon=int(config["horizon"]),
        refit_start=start.date(),
        refit_end=end.date(),
        refit_rows=int(((daily.index >= start) & (daily.index <= end)).sum()),
        n_estimators=int(hyper["n_estimators"]),
        max_depth=int(hyper["max_depth"]),
        min_samples_leaf=int(hyper["min_samples_leaf"]),
    )


def aqi_scale() -> pd.DataFrame:
    """The six US EPA categories with integer bounds (0-50, 51-100, ..., 301 and above)."""
    rows, lower = [], 0
    for label, upper, color in AQI_CATEGORIES:
        rows.append(
            {
                "label": label,
                "lower": lower,
                "upper": None if upper == float("inf") else int(upper),
                "color": color,
            }
        )
        lower = int(upper) + 1 if upper != float("inf") else lower
    return pd.DataFrame(rows)
