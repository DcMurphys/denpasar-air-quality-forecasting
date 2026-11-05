"""Forecast helpers: history window and the two-tier advisory rule (NB §8.2, §9.5)."""

from datetime import UTC, date, datetime

import pandas as pd
import pytest

from aqi_forecasting.config import DATA_DIR
from dashboard.models import forecast as fc


@pytest.fixture(scope="module")
def latest() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "forecast_latest.parquet")


def test_history_is_the_last_60_days(dashboard_daily: pd.DataFrame) -> None:
    history = fc.history(dashboard_daily)
    assert len(history) == 60
    assert history["date"].iloc[-1] == pd.Timestamp("2026-10-30")


def test_current_artifact_triggers_no_advisory(
    latest: pd.DataFrame, dashboard_daily: pd.DataFrame
) -> None:
    adv = fc.advisory(latest, dashboard_daily)
    assert adv.level == "none" and adv.trigger_days == ()
    assert round(adv.max_high, 1) == 67.1  # highest P90 over days 1-3 (NB §8.2 table)
    assert round(latest["aqi_high"].max(), 1) == 69.8  # NB §8.2: highest band, all 7 days
    assert not adv.dry and not adv.calm  # rain in the last 3 days; wind 20.3 km/h


def test_tier1_and_tier2(latest: pd.DataFrame, dashboard_daily: pd.DataFrame) -> None:
    high = latest.assign(aqi_high=latest["aqi_high"].where(latest["horizon"] != 2, 105.0))
    assert fc.advisory(high, dashboard_daily).level == "tier1"
    assert fc.advisory(high, dashboard_daily).trigger_days == (2,)

    dry_calm = dashboard_daily.copy()
    dry_calm.iloc[-3:, dry_calm.columns.get_loc("precipitation_sum")] = 0.5  # under 1 mm (Q8)
    dry_calm.iloc[-1, dry_calm.columns.get_loc("wind_speed_10m_max")] = 10.0
    assert fc.advisory(high, dry_calm).level == "tier2"
    assert fc.advisory(latest, dry_calm).level == "none"  # Tier 2 needs Tier 1

    late = latest.assign(aqi_high=latest["aqi_high"].where(latest["horizon"] != 5, 120.0))
    assert fc.advisory(late, dashboard_daily).level == "none"  # outlook days never trigger


def test_history_windows(dashboard_daily: pd.DataFrame) -> None:
    assert fc.HISTORY_WINDOWS == (14, 60)
    assert len(fc.history(dashboard_daily, fc.SHORT_HISTORY_DAYS)) == 14


# ===== Today and tomorrow (UX review, priority 1) =====
def test_local_today_uses_denpasar_time() -> None:
    # 2026-11-03 17:00 UTC is already 2026-11-04 01:00 in Denpasar (WITA, UTC+8).
    assert fc.local_today(datetime(2026, 11, 3, 17, 0, tzinfo=UTC)) == date(2026, 11, 4)


def test_day_outlook_sources(latest: pd.DataFrame, dashboard_daily: pd.DataFrame) -> None:
    observed = fc.day_outlook(dashboard_daily, latest, date(2026, 10, 30))
    assert observed.source == fc.OBSERVED and observed.category == "Moderate"
    near = fc.day_outlook(dashboard_daily, latest, date(2026, 11, 1))
    assert near.source == fc.FORECAST and near.horizon == 2
    today = fc.day_outlook(dashboard_daily, latest, date(2026, 11, 4))
    assert today.source == fc.OUTLOOK and today.horizon == 5 and round(today.aqi, 1) == 55.9
    beyond = fc.day_outlook(dashboard_daily, latest, date(2026, 11, 7))
    assert beyond.source == fc.UNAVAILABLE and beyond.category is None
    assert fc.day_outlook(dashboard_daily, None, date(2026, 11, 4)).source == fc.UNAVAILABLE


def test_data_age_and_relative_days(dashboard_daily: pd.DataFrame) -> None:
    today = date(2026, 11, 4)
    assert fc.data_age_days(dashboard_daily, today) == 5
    assert [fc.relative_day(date(2026, 11, d), today) for d in (3, 4, 5, 6)] == [
        "past",
        "today",
        "tomorrow",
        "later",
    ]


def test_sensitive_risk_starts_at_usg() -> None:
    day = date(2026, 11, 4)
    assert not fc.DayOutlook(day, fc.OUTLOOK, category="Moderate").is_sensitive_risk
    assert fc.DayOutlook(
        day, fc.OUTLOOK, category="Unhealthy for Sensitive Groups"
    ).is_sensitive_risk
