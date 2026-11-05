"""Large "Today" / "Tomorrow" cards with plain-language advice (UX review, priorities 1-2).

Advice follows US EPA cautionary statements for particle pollution (Technical Assistance
Document for the Reporting of Daily Air Quality – the AQI, May 2026, Tables 4-5); PM2.5 drives
Denpasar's AQI (NB §4.5.4).
"""

from html import escape

import streamlit as st

from dashboard.models.forecast import FORECAST, OBSERVED, DayOutlook
from dashboard.views.components.aqi_badge import badge_html
from dashboard.views.components.palette import BLACK, BORDER, MUTED_TEXT, RED, WHITE
from dashboard.views.i18n import Translator, category_key

_GRID = (
    "display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));"
    "gap:0.75rem;align-items:stretch;margin-bottom:0.75rem;"
)
_CARD = (
    f"background:{WHITE};border:1px solid {BORDER};border-left:6px solid {RED};"
    "border-radius:0.5rem;padding:1rem 1.1rem;"
)
_TITLE = f"font-size:1.05rem;font-weight:600;color:{BLACK};"
_VALUE = f"font-size:2.5rem;font-weight:700;color:{BLACK};line-height:1.1;margin:0.35rem 0;"
_NOTE = f"font-size:0.95rem;color:{MUTED_TEXT};margin:0.4rem 0 0.6rem;"
_ADVICE = f"font-size:1.05rem;color:{BLACK};line-height:1.5;margin:0.35rem 0 0;"


def _advice_key(category: str) -> str:
    return "advice." + category_key(category).removeprefix("aqi.category.")


def day_card_html(tr: Translator, title: str, outlook: DayOutlook) -> str:
    parts = [f'<div class="day-card" style="{_CARD}"><div style="{_TITLE}">{escape(title)}</div>']
    if outlook.category is None:
        parts.append(f'<p style="{_ADVICE}">{escape(tr.t("today.source.unavailable"))}</p></div>')
        return "".join(parts)

    parts.append(f'<div class="day-value" style="{_VALUE}">{escape(tr.number(outlook.aqi))}</div>')
    parts.append(badge_html(tr, outlook.category))
    if outlook.source == OBSERVED:
        note = tr.t("today.source.observed")
    else:
        key = "today.source.forecast" if outlook.source == FORECAST else "today.source.outlook"
        note = (
            tr.t(key, day=outlook.horizon)
            + " · "
            + tr.t("today.range", low=tr.number(outlook.aqi_low), high=tr.number(outlook.aqi_high))
        )
    parts.append(f'<div style="{_NOTE}">{escape(note)}</div>')

    base = _advice_key(outlook.category)
    for who in ("everyone", "sensitive"):
        label = escape(tr.t(f"advice.{who}"))
        text = escape(tr.t(f"{base}.{who}"))
        parts.append(f'<p class="advice" style="{_ADVICE}"><strong>{label}:</strong> {text}</p>')
    if outlook.is_sensitive_risk:
        parts.append(f'<p style="{_ADVICE}">{escape(tr.t("advice.medical"))}</p>')
    parts.append("</div>")
    return "".join(parts)


def day_cards(tr: Translator, cards: list[tuple[str, DayOutlook]]) -> None:
    html = "".join(day_card_html(tr, title, outlook) for title, outlook in cards)
    st.markdown(f'<div class="day-grid" style="{_GRID}">{html}</div>', unsafe_allow_html=True)
