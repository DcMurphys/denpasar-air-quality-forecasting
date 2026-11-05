"""Small responsive HTML tables, for cells that need markup (e.g. AQI category badges)."""

from html import escape

import streamlit as st

from dashboard.views.components.palette import BORDER, MUTED_TEXT, RED_TINT

_WRAP = "overflow-x:auto;margin-bottom:1rem;"
_TABLE = "width:100%;border-collapse:collapse;font-size:0.95rem;"
_TH = (
    f"text-align:left;padding:0.45rem 0.6rem;border-bottom:2px solid {BORDER};"
    f"color:{MUTED_TEXT};font-weight:600;"
)
_HIGHLIGHT = f"background:{RED_TINT};"
_CAPTION = "text-align:left;font-weight:600;padding-bottom:0.4rem;"
_TD = f"padding:0.45rem 0.6rem;border-bottom:1px solid {BORDER};vertical-align:middle;"


def html_table(
    columns: list[str],
    rows: list[list[str]],
    *,
    raw_columns: set[int] = frozenset(),
    css_class: str = "",
    caption: str = "",
    highlight_rows: frozenset[int] = frozenset(),
) -> None:
    """Render a table; cells in ``raw_columns`` are trusted HTML, all others are escaped.

    Rows in ``highlight_rows`` get a tinted background (always paired with a text cue in
    the row itself, so the highlight is never colour-only).
    """
    head = "".join(f'<th scope="col" style="{_TH}">{escape(c)}</th>' for c in columns)
    body = "".join(
        "<tr>"
        + "".join(
            f'<td style="{_TD}{_HIGHLIGHT if r in highlight_rows else ""}">'
            f"{cell if i in raw_columns else escape(cell)}</td>"
            for i, cell in enumerate(row)
        )
        + "</tr>"
        for r, row in enumerate(rows)
    )
    cap = f'<caption style="{_CAPTION}">{escape(caption)}</caption>' if caption else ""
    st.markdown(
        f'<div style="{_WRAP}"><table class="{escape(css_class)}" style="{_TABLE}">{cap}'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>",
        unsafe_allow_html=True,
    )
