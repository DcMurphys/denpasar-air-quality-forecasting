"""Calendar, regime, and forecasting features, identical to the notebook (NB §4.5, §5.1).

The notebook and the dashboard both import these functions, so features are computed the same
way in training and in the app.
"""

import numpy as np
import pandas as pd

from aqi_forecasting.config import (
    AQI_LAGS,
    CAMS_UPGRADES,
    DAYS_PER_YEAR,
    MAX_FFILL_DAYS,
    MODEL_REGIME_FLAGS,
    N_HARMONICS,
    POLLUTANT_COLS,
    RAIN_SUM_WINDOWS,
    ROLLING_STATS,
    ROLLING_WINDOWS,
    TARGET,
    WEATHER_COLS,
    WET_SEASON_MONTHS,
)


def season_labels(index: pd.DatetimeIndex) -> np.ndarray:
    """Label each date as "Wet" (November–March) or "Dry" (April–October)."""
    return np.where(index.month.isin(WET_SEASON_MONTHS), "Wet", "Dry")


def fourier_terms(index: pd.DatetimeIndex, n_harmonics: int) -> dict[str, np.ndarray]:
    """Return sin/cos day-of-year terms for the first ``n_harmonics`` annual harmonics.

    Shared by the seasonal analysis and by ``build_features``.
    """
    angle = 2 * np.pi * index.dayofyear.to_numpy() / DAYS_PER_YEAR
    return {
        f"{func.__name__}_doy_{k}": func(k * angle)
        for k in range(1, n_harmonics + 1)
        for func in (np.sin, np.cos)
    }


def add_regime_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add 0/1 flags for days on or after each CAMS model upgrade (expects a DatetimeIndex)."""
    return df.assign(
        **{
            name: (df.index >= pd.Timestamp(date)).astype("int8")
            for name, date in CAMS_UPGRADES.items()
        }
    )


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build causal forecasting features: every feature uses data up to day t only."""
    exog = df[POLLUTANT_COLS + WEATHER_COLS].ffill(limit=MAX_FFILL_DAYS)
    aqi, rain = df[TARGET], exog["precipitation_sum"]
    engineered = {
        "aqi_t": aqi,
        **{f"aqi_t-{lag}": aqi.shift(lag) for lag in AQI_LAGS},
        **{
            f"aqi_roll{w}_{stat}": getattr(aqi.rolling(w, min_periods=w), stat)()
            for w in ROLLING_WINDOWS
            for stat in ROLLING_STATS
        },
        **{f"precip_sum_{w}d": rain.rolling(w, min_periods=w).sum() for w in RAIN_SUM_WINDOWS},
        **fourier_terms(df.index, N_HARMONICS),
    }
    return pd.concat(
        [pd.DataFrame(engineered, index=df.index), exog, add_regime_flags(df)[MODEL_REGIME_FLAGS]],
        axis=1,
    )
