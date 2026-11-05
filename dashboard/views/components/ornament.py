"""Decorative Tridatu ribbon (white, red, black) shown at the top of every page."""

import streamlit as st

from dashboard.views.components.palette import BLACK, BORDER, RED, WHITE


def ribbon_html() -> str:
    bands = "".join(
        f'<div style="flex:1;background:{color}"></div>' for color in (WHITE, RED, BLACK)
    )
    style = (
        f"display:flex;height:6px;border:1px solid {BORDER};border-radius:3px;overflow:hidden;"
        "margin-bottom:0.25rem;"
    )
    return f'<div class="tridatu-ribbon" role="presentation" style="{style}">{bands}</div>'


def tridatu_ribbon() -> None:
    st.markdown(ribbon_html(), unsafe_allow_html=True)
