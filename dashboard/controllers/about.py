"""About page (scope §4.4). It reads only metadata, so it renders even when the forecast or
prediction files are missing."""

import logging

from dashboard.controllers import data
from dashboard.controllers.language import translator
from dashboard.models import baseline, metadata
from dashboard.models.artifacts import ArtifactError
from dashboard.views import about as view

logger = logging.getLogger(__name__)


def render() -> None:
    tr = translator()
    daily = data.dashboard_daily()
    config = data.preprocessing_config()
    view.intro(tr)
    view.data_section(tr, metadata.data_facts(daily, config))
    view.aqi_section(tr, metadata.aqi_scale())
    try:
        params = data.model_params(config)
    except ArtifactError as err:
        logger.error("Model parameters unavailable on About: %s", err)
        view.model_error(tr, err)
    else:
        view.model_section(tr, metadata.model_facts(daily, config, params))
    view.use_section(tr, int(config["horizon"]))
    view.glossary_section(tr, int(config["horizon"]))
    status = baseline.current_status(daily)
    view.limits_section(
        tr,
        extreme_days=status.days_above_100,
        history_years=round(status.n_days / 365.25),
    )
