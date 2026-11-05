"""App shell: page config, language toggle, navigation, sidebar, and fatal-error handling."""

import logging
from pathlib import Path

import streamlit as st

from dashboard.controllers import data
from dashboard.controllers.language import select_language
from dashboard.models.artifacts import ArtifactError, data_version_matches
from dashboard.views import shell
from dashboard.views.components import notices
from dashboard.views.components.ornament import tridatu_ribbon
from dashboard.views.components.palette import JEPUN_ICON_SVG
from dashboard.views.components.style import inject_global_css

logger = logging.getLogger(__name__)

PAGE_DIR = Path(__file__).resolve().parents[1] / "page_scripts"
PAGE_IDS = ("overview", "drivers", "forecast", "about")
PAGES_KEY = "pages"


def run() -> None:
    """Build the app for one rerun and run the selected page."""
    st.set_page_config(layout="wide", page_icon=str(JEPUN_ICON_SVG))
    inject_global_css()
    tridatu_ribbon()
    translator, missing_locales = select_language()
    pages = {
        page_id: st.Page(
            PAGE_DIR / f"{page_id}.py",
            title=translator.t(f"page.{page_id}"),
            url_path=page_id,
            default=page_id == "overview",
        )
        for page_id in PAGE_IDS
    }
    st.session_state[PAGES_KEY] = pages
    selected = st.navigation(list(pages.values()))
    # Descriptive browser tab title; the short st.Page title stays in the sidebar list.
    page_id = next((pid for pid, page in pages.items() if page is selected), "overview")
    st.set_page_config(page_title=shell.tab_title(translator, page_id))

    for lang in missing_locales:
        notices.warning(translator.t("warning.locale_missing", lang=lang))

    # dashboard_daily and preprocessing_config are required by every page (scope §5 policy).
    try:
        daily = data.dashboard_daily()
        config = data.preprocessing_config()
    except ArtifactError as err:
        logger.error("Fatal artifact error: %s", err)
        notices.fatal_error(translator, err)
        return

    if not data_version_matches(daily, config["data_version"]):
        logger.warning("data_version mismatch: expected %s", config["data_version"])
        notices.warning(translator.t("warning.data_version"))

    shell.sidebar(
        translator,
        start=daily.index[0],
        end=daily.index[-1],
        data_version=config["data_version"],
        about_page=pages["about"],
    )
    selected.run()
