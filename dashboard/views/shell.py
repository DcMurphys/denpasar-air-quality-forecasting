"""Shell views: browser tab title and sidebar facts."""

from datetime import date

import streamlit as st

from dashboard.views.components import notices
from dashboard.views.components.palette import JEPUN_IMAGE
from dashboard.views.components.sources import sources_markdown
from dashboard.views.i18n import Translator


def tab_title(tr: Translator, page_id: str) -> str:
    """Browser tab title: a descriptive page name first (tabs truncate), then the app name."""
    return tr.t("tab.format", page=tr.t(f"tab.{page_id}"), app=tr.t("app.title"))


def sidebar(tr: Translator, *, start: date, end: date, data_version: str, about_page) -> None:
    with st.sidebar:
        # Decorative bunga jepun (see palette.JEPUN_IMAGE), served as the jepun.png file itself.
        # A 140 px box with a stretched image: an integer width would make Streamlit downscale
        # the 280 px file to 140 px, which looks soft on high-density screens. PNG output stops
        # Streamlit from re-encoding the opaque PNG as a JPEG ("auto").
        with st.container(width=140):
            st.image(str(JEPUN_IMAGE), width="stretch", output_format="PNG")
        st.markdown(f"**{tr.t('app.title')}**")
        st.caption(tr.t("sidebar.data_period", start=tr.date(start), end=tr.date(end)))
        st.caption(tr.t("sidebar.data_version", version=data_version))
        notices.info(tr.t("sidebar.caveat"))
        st.caption(sources_markdown(tr))
        st.page_link(about_page, label=tr.t("sidebar.about_link"), icon=":material/arrow_forward:")
