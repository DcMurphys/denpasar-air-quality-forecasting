"""Key Factors page (scope §4.2)."""

import logging

import pandas as pd
import streamlit as st

from dashboard.controllers import data
from dashboard.controllers.language import translator
from dashboard.models import drivers
from dashboard.models.artifacts import ArtifactError
from dashboard.views import drivers as view

logger = logging.getLogger(__name__)


@st.cache_data(show_spinner=False)
def _spearman(daily: pd.DataFrame) -> pd.DataFrame:
    return drivers.spearman_ranking(daily)


def render() -> None:
    tr = translator()
    daily = data.dashboard_daily()
    config = data.preprocessing_config()
    ranking = _spearman(daily)

    importance, importance_error = None, None
    try:
        importance = data.feature_importance(config["feature_columns"])
    except ArtifactError as err:
        logger.error("Feature importance unavailable: %s", err)
        importance_error = err

    view.header(tr, drivers.findings(daily, ranking, importance))
    horizon = view.horizon_toggle(tr)
    view.correlations(tr, ranking, horizon)
    if importance_error is not None:
        view.importance_error(tr, importance_error)
    else:
        view.importance(
            tr,
            drivers.importance_ranking(importance),
            excluded=drivers.n_without_contribution(importance),
        )
