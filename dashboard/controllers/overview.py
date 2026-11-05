"""Overview page: today/tomorrow, summary KPIs, and the history tabs (scope §4.1)."""

import logging
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from dashboard.controllers import data
from dashboard.controllers.language import translator
from dashboard.models import baseline, forecast
from dashboard.models.artifacts import ArtifactError
from dashboard.views import overview

logger = logging.getLogger(__name__)


@st.cache_data(show_spinner=False)
def _history(daily: pd.DataFrame, season: str, years: tuple[int, int]) -> dict[str, pd.DataFrame]:
    """Derived tables for one filter combination; language-independent, so cached once."""
    return {
        "annual": baseline.annual_kpis(daily, season, years),
        "profile": baseline.monthly_profile(daily, season, years),
        "seasons": baseline.season_means(daily, season, years),
        "unhealthy": baseline.unhealthy_days(daily, season, years),
    }


@st.cache_data(show_spinner=False)
def _trend(
    daily: pd.DataFrame,
    season: str,
    years: tuple[int, int],
    variable: str,
    dates: tuple[date, date],
) -> pd.DataFrame:
    return baseline.trend(daily, season, years, column=variable, dates=dates)


def render() -> None:
    tr = translator()
    daily = data.dashboard_daily()
    config = data.preprocessing_config()

    # Today and tomorrow first (UX review): observed or forecast AQI with plain advice.
    today = data.today()
    latest, forecast_error = None, None
    try:
        latest = data.forecast(last_date=forecast.issue_date(daily))
    except ArtifactError as err:
        logger.error("Forecast unavailable on Overview: %s", err)
        forecast_error = err
    overview.today_block(
        tr,
        today=forecast.day_outlook(daily, latest, today),
        tomorrow=forecast.day_outlook(daily, latest, today + timedelta(days=1)),
        last_date=forecast.issue_date(daily),
        age_days=forecast.data_age_days(daily, today),
        forecast_error=forecast_error,
        forecast_page=st.session_state["pages"]["forecast"],
    )

    # Summary KPIs: whole period, never filtered.
    status = baseline.current_status(daily)
    if status.who_share is None:
        logger.warning("exceeds_who_pm25 is inconsistent with pm2_5_mean > 15; WHO card hidden")
    overview.current_status(tr, status)

    # History tabs: shared year-range and season filters.
    bounds = baseline.year_bounds(daily)
    years, season = overview.history_filters(tr, bounds)
    tables = _history(daily, season, years)
    overview.history_tabs(
        tr,
        **tables,
        trend_for=lambda variable, dates: _trend(daily, season, years, variable, dates),
        date_range=baseline.date_bounds(daily, years),
        all_years=list(range(bounds[0], bounds[1] + 1)),
        cams={key.removeprefix("post_cams_"): day for key, day in config["cams_upgrades"].items()},
    )
