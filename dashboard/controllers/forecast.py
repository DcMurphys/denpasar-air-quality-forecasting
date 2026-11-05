"""7-Day Forecast page (scope §4.3): forecast and Reliability sections."""

import logging

import pandas as pd
import streamlit as st

from dashboard.controllers import data
from dashboard.controllers.language import translator
from dashboard.models import forecast, performance
from dashboard.models.artifacts import ArtifactError
from dashboard.views import forecast as view

logger = logging.getLogger(__name__)


def render() -> None:
    tr = translator()
    daily = data.dashboard_daily()
    issued = forecast.issue_date(daily)
    view.header(tr, issued)
    try:
        latest = data.forecast(last_date=issued)
    except ArtifactError as err:
        logger.error("Forecast unavailable: %s", err)
        view.forecast_error(tr, err)
        return
    view.advisory_panel(tr, forecast.advisory(latest, daily), issued)
    today = data.today()
    days = view.history_window(tr)
    view.forecast_chart(tr, forecast.history(daily, days), latest, today)
    view.forecast_tables(tr, latest, today)
    _reliability(tr, daily)


@st.cache_data(show_spinner=False)
def _evaluation(predictions: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    return performance.per_horizon(performance.evaluation_long(predictions, daily))


def _reliability(tr, daily: pd.DataFrame) -> None:
    """Reliability section; a missing predictions or metrics file only affects this section."""
    config = data.preprocessing_config()
    test_bounds = config["split_bounds"]["test"]
    try:
        predictions = data.predictions(test_bounds)
        metrics = data.metrics()
    except ArtifactError as err:
        logger.error("Reliability unavailable: %s", err)
        view.reliability_error(tr, err)
        return
    per_h = _evaluation(predictions, daily)
    view.reliability(
        tr,
        card=performance.scorecard(per_h),
        per_h=per_h,
        table=performance.summary(per_h),
        regime=performance.regime_table(metrics),
        test_bounds=test_bounds,
        avp_for=lambda horizon: performance.actual_vs_predicted(predictions, horizon),
        cams_50r1=config["cams_upgrades"]["post_cams_50r1"],
    )
