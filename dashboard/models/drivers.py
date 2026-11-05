"""Key factors behind AQI (scope §4.2, criteria B2 / D2).

Spearman correlations are recomputed from ``dashboard_daily.parquet`` (NB §4.5.4); permutation
importance is read from ``feature_importance_rf_tuned.csv`` (NB §7.7).
"""

from dataclasses import dataclass

import pandas as pd

from aqi_forecasting.config import POLLUTANT_FEATURES, TARGET, WEATHER_FEATURES

SAME_DAY, NEXT_DAY = "same_day", "next_day"
HORIZONS = (SAME_DAY, NEXT_DAY)
POLLUTANT, WEATHER = "pollutant", "weather"
TOP_N_IMPORTANCE = 10
# Importance at or below this is "no measurable contribution" (shuffling does not raise RMSE).
MIN_IMPORTANCE = 1e-9


def spearman_ranking(daily: pd.DataFrame) -> pd.DataFrame:
    """Spearman ρ of every pollutant and weather variable with same-day and next-day AQI.

    The daily index is contiguous, so ``shift(-1)`` is the next calendar day.
    """
    aqi = daily[TARGET]
    groups = {
        **dict.fromkeys(POLLUTANT_FEATURES, POLLUTANT),
        **dict.fromkeys(WEATHER_FEATURES, WEATHER),
    }
    columns = list(groups)
    table = pd.DataFrame(
        {
            SAME_DAY: daily[columns].corrwith(aqi, method="spearman"),
            NEXT_DAY: daily[columns].corrwith(aqi.shift(-1), method="spearman"),
        }
    ).rename_axis("variable")
    table["group"] = table.index.map(groups)
    return table.reset_index()


def importance_ranking(importance: pd.DataFrame, top_n: int = TOP_N_IMPORTANCE) -> pd.DataFrame:
    """Top features with a positive permutation importance (RMSE increase, AQI points)."""
    positive = importance.loc[importance["importance"] > MIN_IMPORTANCE]
    top = positive.sort_values("importance", ascending=False).head(top_n)
    return top.rename_axis("feature").reset_index()


def n_without_contribution(importance: pd.DataFrame) -> int:
    """Features whose shuffling does not raise RMSE (importance at or below zero)."""
    return int((importance["importance"] <= MIN_IMPORTANCE).sum())


@dataclass(frozen=True)
class Findings:
    """Numbers for the plain-language findings panel (NB §9.1, §9.5)."""

    pm25_same: float
    pm25_next: float
    pm10_same: float
    o3_same: float
    rain_hours_same: float
    rain_hours_next: float
    wind_no2: float
    wind_co: float
    persistence: float
    top_features: tuple[str, ...] | None  # None when the importance file is unavailable


def findings(
    daily: pd.DataFrame, spearman: pd.DataFrame, importance: pd.DataFrame | None
) -> Findings:
    rho = spearman.set_index("variable")
    wind = daily["wind_speed_10m_max"]
    aqi = daily[TARGET]
    top = None if importance is None else tuple(importance_ranking(importance)["feature"].head(3))
    return Findings(
        pm25_same=float(rho.loc["pm2_5_mean", SAME_DAY]),
        pm25_next=float(rho.loc["pm2_5_mean", NEXT_DAY]),
        pm10_same=float(rho.loc["pm10_mean", SAME_DAY]),
        o3_same=float(rho.loc["ozone_mean", SAME_DAY]),
        rain_hours_same=float(rho.loc["precipitation_hours", SAME_DAY]),
        rain_hours_next=float(rho.loc["precipitation_hours", NEXT_DAY]),
        wind_no2=float(wind.corr(daily["nitrogen_dioxide_mean"], method="spearman")),
        wind_co=float(wind.corr(daily["carbon_monoxide_mean"], method="spearman")),
        persistence=float(aqi.corr(aqi.shift(-1), method="spearman")),
        top_features=top,
    )
