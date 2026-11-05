"""Baseline KPIs, trend, and seasonality from ``dashboard_daily.parquet`` (scope §4.1, B1 / D1)."""

import calendar
from dataclasses import dataclass
from datetime import date

import pandas as pd

from aqi_forecasting.config import (
    POLLUTANT_FEATURES,
    TARGET,
    TREND_ROLLING_WINDOW,
    WEATHER_FEATURES,
)
from dashboard.models.artifacts import who_flag_consistent

UNHEALTHY_THRESHOLD = 100  # AQI above which a day counts as an exceedance (NB §2.2, D1)
ALL_SEASONS = "all"
SEASONS = (ALL_SEASONS, "Dry", "Wet")

YearRange = tuple[int, int]
# Variables an expert can plot on the Trend tab (UX priority 8): the AQI, then pollutants and
# weather in the notebook's catalogue order (NB §3.2).
TREND_VARIABLES = (TARGET, *POLLUTANT_FEATURES, *WEATHER_FEATURES)


@dataclass(frozen=True)
class CurrentStatus:
    """Headline KPIs for the Overview's Current status block."""

    latest_date: pd.Timestamp
    latest_aqi: float
    latest_category: str
    mean_aqi: float
    n_days: int
    days_above_100: int
    share_above_100: float  # percent
    dry_mean: float
    wet_mean: float
    mean_pm25: float
    who_share: float | None  # percent; None when the WHO flag is inconsistent (decision Q6)


def current_status(daily: pd.DataFrame) -> CurrentStatus:
    """Compute the Current status KPIs over the whole period (not affected by filters)."""
    aqi = daily[TARGET]
    above = aqi > UNHEALTHY_THRESHOLD
    season_means = aqi.groupby(daily["season"].astype(str)).mean()
    who_share = daily["exceeds_who_pm25"].mean() * 100 if who_flag_consistent(daily) else None
    return CurrentStatus(
        latest_date=daily.index[-1],
        latest_aqi=float(aqi.iloc[-1]),
        latest_category=str(daily["aqi_category"].iloc[-1]),
        mean_aqi=float(aqi.mean()),
        n_days=len(daily),
        days_above_100=int(above.sum()),
        share_above_100=float(above.mean() * 100),
        dry_mean=float(season_means["Dry"]),
        wet_mean=float(season_means["Wet"]),
        mean_pm25=float(daily["pm2_5_mean"].mean()),
        who_share=None if who_share is None else float(who_share),
    )


# ===== Filters (Overview tabs) =====
def _in_season(daily: pd.DataFrame, season: str) -> pd.Series:
    if season == ALL_SEASONS:
        return pd.Series(True, index=daily.index)
    return daily["season"].astype(str) == season


def _in_years(index: pd.DatetimeIndex, years: YearRange) -> pd.Series:
    return pd.Series((index.year >= years[0]) & (index.year <= years[1]), index=index)


def year_bounds(daily: pd.DataFrame) -> YearRange:
    return int(daily.index.year.min()), int(daily.index.year.max())


def partial_years(daily: pd.DataFrame) -> set[int]:
    """Years not fully covered by the data (2022 and 2026 in the current artifact)."""
    counts = daily.groupby(daily.index.year).size()
    return {
        int(year) for year, n in counts.items() if n < (366 if calendar.isleap(int(year)) else 365)
    }


def annual_kpis(daily: pd.DataFrame, season: str, years: YearRange) -> pd.DataFrame:
    """Annual table of NB §4.5.2: days, mean AQI, % days above 100, and YoY change.

    YoY is computed over all years before the year filter is applied, so a filtered first
    year keeps its change against the previous year.
    """
    aqi = daily.loc[_in_season(daily, season), TARGET]
    grouped = aqi.groupby(aqi.index.year)
    table = pd.DataFrame(
        {
            "days": grouped.size(),
            "mean_aqi": grouped.mean(),
            "pct_days_above_100": grouped.apply(lambda s: (s > UNHEALTHY_THRESHOLD).mean() * 100),
        }
    ).rename_axis("year")
    table["yoy_change_pct"] = table["mean_aqi"].pct_change() * 100
    table["partial"] = table.index.isin(partial_years(daily))
    return table.loc[years[0] : years[1]].reset_index()


def trend(
    daily: pd.DataFrame,
    season: str,
    years: YearRange,
    *,
    column: str = TARGET,
    dates: tuple[date, date] | None = None,
) -> pd.DataFrame:
    """Daily values of ``column`` with the centred 30-day rolling mean of the NB §4.5.1 helper.

    The rolling mean uses the full series; days outside the filters (season, years, and the
    optional inclusive ``dates`` range) are dropped, and ``segment`` numbers each contiguous
    run so that charts break the line at the gaps.
    """
    values = daily[column]
    rolling = values.rolling(
        TREND_ROLLING_WINDOW, min_periods=TREND_ROLLING_WINDOW // 2, center=True
    ).mean()
    keep = _in_season(daily, season) & _in_years(daily.index, years)
    if dates is not None:
        keep &= (daily.index >= pd.Timestamp(dates[0])) & (daily.index <= pd.Timestamp(dates[1]))
    segment = (keep != keep.shift()).cumsum()
    frame = pd.DataFrame(
        {
            "date": daily.index,
            "value": values.to_numpy(),
            "rolling_mean": rolling.to_numpy(),
            "segment": segment.to_numpy(),
        }
    )
    return frame.loc[keep.to_numpy()].reset_index(drop=True)


def date_bounds(daily: pd.DataFrame, years: YearRange) -> tuple[date, date]:
    """First and last observed day inside the selected years."""
    inside = daily.index[_in_years(daily.index, years).to_numpy()]
    return inside[0].date(), inside[-1].date()


def monthly_profile(daily: pd.DataFrame, season: str, years: YearRange) -> pd.DataFrame:
    """Mean AQI per year and calendar month (long format: year, month, mean_aqi)."""
    keep = _in_season(daily, season) & _in_years(daily.index, years)
    aqi = daily.loc[keep, TARGET]
    profile = aqi.groupby([aqi.index.year, aqi.index.month]).mean()
    return profile.rename_axis(["year", "month"]).rename("mean_aqi").reset_index()


def season_means(daily: pd.DataFrame, season: str, years: YearRange) -> pd.DataFrame:
    """Mean AQI and day count per season (season label kept in English as a key)."""
    keep = _in_season(daily, season) & _in_years(daily.index, years)
    subset = daily.loc[keep]
    grouped = subset[TARGET].groupby(subset["season"].astype(str))
    return (
        pd.DataFrame({"mean_aqi": grouped.mean(), "days": grouped.size()})
        .rename_axis("season")
        .reset_index()
    )


def unhealthy_days(daily: pd.DataFrame, season: str, years: YearRange) -> pd.DataFrame:
    """Days with AQI above 100, oldest first (date, aqi, category)."""
    keep = _in_season(daily, season) & _in_years(daily.index, years)
    above = daily.loc[keep & (daily[TARGET] > UNHEALTHY_THRESHOLD)]
    return pd.DataFrame(
        {
            "date": above.index,
            "aqi": above[TARGET].to_numpy(),
            "category": above["aqi_category"].astype(str).to_numpy(),
        }
    )
