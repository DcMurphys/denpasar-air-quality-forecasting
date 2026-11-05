"""US AQI category badge: the category colour always paired with its translated label."""

from html import escape

import streamlit as st

from aqi_forecasting.config import AQI_CATEGORIES
from dashboard.views.i18n import Translator

_COLORS = {label: color for label, _, color in AQI_CATEGORIES}
# Dark text on the light category colours (Good, Moderate, USG), white text on the dark ones.
_LIGHT_BACKGROUNDS = {"Good", "Moderate", "Unhealthy for Sensitive Groups"}


def badge_html(tr: Translator, label: str, *, with_scale: bool = True, wrap: bool = False) -> str:
    """HTML for one category badge, e.g. "US AQI: Sedang" on a yellow background.

    ``with_scale=False`` drops the "US AQI:" prefix where a column header already names the
    scale, so narrow tables fit on phones; ``wrap=True`` lets a long label break over two
    lines instead of widening its column.
    """
    name = tr.category(label)
    text = tr.t("aqi.badge", scale=tr.t("aqi.scale"), category=name) if with_scale else name
    foreground = "#1a1a1a" if label in _LIGHT_BACKGROUNDS else "#ffffff"
    style = (
        f"background:{_COLORS[label]};color:{foreground};padding:2px 10px;"
        "border-radius:999px;font-size:0.85rem;font-weight:600;display:inline-block;"
        + ("" if wrap else "white-space:nowrap;")
    )
    return f'<span style="{style}">{escape(text)}</span>'


def badge(tr: Translator, label: str) -> None:
    st.markdown(badge_html(tr, label), unsafe_allow_html=True)
