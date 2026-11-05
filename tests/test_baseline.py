"""Current status KPIs reproduce NB §4.5.2 and §9.1 (scope §4.1)."""

import pandas as pd
import pytest

from dashboard.models.baseline import (
    ALL_SEASONS,
    annual_kpis,
    current_status,
    monthly_profile,
    partial_years,
    season_means,
    trend,
    unhealthy_days,
)


def test_current_status_matches_notebook(dashboard_daily: pd.DataFrame) -> None:
    status = current_status(dashboard_daily)
    assert status.latest_date == pd.Timestamp("2026-10-30")
    assert status.n_days == 1548
    assert status.days_above_100 == 5
    assert round(status.share_above_100, 1) == 0.3
    assert round(status.dry_mean, 1) == 52.4
    assert round(status.wet_mean, 1) == 51.3
    assert round(status.mean_pm25, 1) == 11.0  # NB §9.1
    assert status.who_share == pytest.approx(12.1, abs=0.05)


def test_who_share_hidden_when_flag_inconsistent(dashboard_daily: pd.DataFrame) -> None:
    broken = dashboard_daily.assign(exceeds_who_pm25=~dashboard_daily["exceeds_who_pm25"])
    assert current_status(broken).who_share is None


# ===== History tabs (scope §4.1, NB §4.5.2) =====
ALL_YEARS = (2022, 2026)


def test_annual_kpis_match_notebook(dashboard_daily: pd.DataFrame) -> None:
    table = annual_kpis(dashboard_daily, ALL_SEASONS, ALL_YEARS).round(2)
    assert table["year"].tolist() == [2022, 2023, 2024, 2025, 2026]
    assert table["days"].tolist() == [149, 365, 366, 365, 303]
    assert table["mean_aqi"].tolist() == [50.63, 52.85, 51.18, 52.21, 52.27]
    assert table["pct_days_above_100"].tolist() == [0.00, 0.27, 0.55, 0.27, 0.33]
    assert table["yoy_change_pct"].tolist()[1:] == [4.39, -3.15, 2.00, 0.12]
    assert table["partial"].tolist() == [True, False, False, False, True]


def test_year_filter_keeps_change_against_previous_year(dashboard_daily: pd.DataFrame) -> None:
    table = annual_kpis(dashboard_daily, ALL_SEASONS, (2024, 2025)).round(2)
    assert table["year"].tolist() == [2024, 2025]
    assert table["yoy_change_pct"].tolist() == [-3.15, 2.00]


def test_season_filter_uses_notebook_definition(dashboard_daily: pd.DataFrame) -> None:
    profile = monthly_profile(dashboard_daily, "Wet", ALL_YEARS)
    assert set(profile["month"]) == {11, 12, 1, 2, 3}
    means = season_means(dashboard_daily, ALL_SEASONS, ALL_YEARS).set_index("season")
    assert means["mean_aqi"].round(1).to_dict() == {"Dry": 52.4, "Wet": 51.3}


def test_trend_rolling_mean_and_gaps(dashboard_daily: pd.DataFrame) -> None:
    full = trend(dashboard_daily, ALL_SEASONS, ALL_YEARS)
    assert len(full) == 1548 and full["segment"].nunique() == 1
    # NB §4.5.2 insight: the 30-day rolling mean moved between roughly 38 and 67.
    assert 37 < full["rolling_mean"].min() < 39 and 66 < full["rolling_mean"].max() < 68
    dry = trend(dashboard_daily, "Dry", (2023, 2024))
    assert dry["segment"].nunique() == 2  # one run per dry season, broken in between


def test_monthly_peak_and_unhealthy_days(dashboard_daily: pd.DataFrame) -> None:
    profile = monthly_profile(dashboard_daily, ALL_SEASONS, ALL_YEARS).set_index(["year", "month"])
    assert round(profile.loc[(2024, 11), "mean_aqi"]) == 66  # NB §4.5.2: November 2024 ≈ 66
    days = unhealthy_days(dashboard_daily, ALL_SEASONS, ALL_YEARS)
    assert len(days) == 5
    assert set(days["date"].dt.month) <= {11, 12, 1, 2}  # NB §9.2: all in November–February
    assert partial_years(dashboard_daily) == {2022, 2026}


# ===== Expert trend controls (UX priority 8) =====
def test_trend_for_any_variable_and_date_range(dashboard_daily: pd.DataFrame) -> None:
    from datetime import date

    from dashboard.models.baseline import TREND_VARIABLES, date_bounds

    assert TREND_VARIABLES[0] == "us_aqi_mean" and len(TREND_VARIABLES) == 13
    window = (date(2025, 1, 1), date(2025, 3, 31))
    pm = trend(dashboard_daily, ALL_SEASONS, ALL_YEARS, column="pm2_5_mean", dates=window)
    assert len(pm) == 90
    assert pm["date"].min() == pd.Timestamp("2025-01-01")
    assert (
        pm["value"].tolist()
        == dashboard_daily.loc["2025-01-01":"2025-03-31", "pm2_5_mean"].tolist()
    )
    assert date_bounds(dashboard_daily, ALL_YEARS) == (date(2022, 8, 5), date(2026, 10, 30))
    assert date_bounds(dashboard_daily, (2024, 2024)) == (date(2024, 1, 1), date(2024, 12, 31))
