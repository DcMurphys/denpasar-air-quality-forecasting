"""KPI cards rendered as one CSS grid per row group (scope §7).

A single grid gives every card in a row the same height and wraps to fewer columns on narrow
screens. Labels and values wrap instead of being truncated (``st.metric`` truncates).
"""

from dataclasses import dataclass
from html import escape

import streamlit as st

from dashboard.views.components.icons import icon_html
from dashboard.views.components.palette import BLACK, BORDER, MUTED_TEXT, RED, WHITE


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    icon: str  # Material Symbols name, e.g. "air"
    extra_html: str = ""  # e.g. an AQI category badge, shown under the value


_GRID_STYLE = (
    "display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));"
    "gap:0.75rem;align-items:stretch;margin-bottom:1rem;"
)
_CARD_STYLE = (
    f"background:{WHITE};border:1px solid {BORDER};border-radius:0.5rem;padding:0.75rem 1rem;"
)
_ACCENT_STYLE = f"border-left:4px solid {RED};padding-left:0.75rem;height:100%;"
_LABEL_STYLE = (
    f"font-size:0.95rem;font-weight:500;color:{MUTED_TEXT};line-height:1.3;overflow-wrap:anywhere;"
    "display:flex;gap:0.35rem;align-items:flex-start;"
)
_VALUE_STYLE = (
    f"font-size:1.5rem;font-weight:700;color:{BLACK};line-height:1.2;margin:0.3rem 0 0.35rem;"
    "overflow-wrap:anywhere;"
)


def kpi_html(kpi: Kpi) -> str:
    return (
        f'<div class="kpi-card" style="{_CARD_STYLE}"><div style="{_ACCENT_STYLE}">'
        f'<div class="kpi-label" style="{_LABEL_STYLE}">{icon_html(kpi.icon, RED)}'
        f"<span>{escape(kpi.label)}</span></div>"
        f'<div class="kpi-value" style="{_VALUE_STYLE}">{escape(kpi.value)}</div>'
        f"{kpi.extra_html}</div></div>"
    )


def kpi_grid(kpis: list[Kpi]) -> None:
    """Render KPI cards side by side; all cards in a row share the tallest card's height."""
    cards = "".join(kpi_html(kpi) for kpi in kpis)
    grid = f'<div class="kpi-grid" style="{_GRID_STYLE}">{cards}</div>'
    st.markdown(grid, unsafe_allow_html=True)
