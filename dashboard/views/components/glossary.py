"""Plain-language explanations of technical terms, next to where they are used (UX priority 4).

An expander rather than hover tooltips: tooltips do not work on touch screens and are easy to
miss with a screen reader.
"""

import streamlit as st

from dashboard.views.i18n import Translator


def glossary(tr: Translator, items: list[tuple[str, dict]]) -> None:
    """Render ``glossary.<key>`` entries, each filled with its placeholder values."""
    with st.expander(tr.t("glossary.heading"), icon=":material/help:"):
        st.markdown("\n".join(f"- {tr.t(f'glossary.{key}', **values)}" for key, values in items))
