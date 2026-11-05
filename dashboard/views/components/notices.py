"""Notices: red-tinted info callouts, warnings, the snapshot label, and error cards."""

from datetime import date
from html import escape

import streamlit as st

from dashboard.models.artifacts import ArtifactError
from dashboard.views.components.icons import icon_html
from dashboard.views.components.palette import BLACK, RED, RED_TINT
from dashboard.views.i18n import Translator

_CALLOUT_STYLE = (
    f"background:{RED_TINT};border-left:4px solid {RED};border-radius:0.5rem;"
    f"padding:0.75rem 1rem;color:{BLACK};line-height:1.45;display:flex;gap:0.6rem;"
    "align-items:flex-start;margin-bottom:1rem;"
)


def callout_html(text: str, icon: str = "info") -> str:
    """Info callout: light red background, red left border, black text (16.6:1)."""
    return (
        f'<div class="info-callout" style="{_CALLOUT_STYLE}">{icon_html(icon, RED, "1.25rem")}'
        f"<span>{escape(text)}</span></div>"
    )


def info(text: str, icon: str = "info") -> None:
    st.markdown(callout_html(text, icon), unsafe_allow_html=True)


def error_message(tr: Translator, err: ArtifactError) -> str:
    """User-facing text for an artifact error; technical details are logged by controllers."""
    return tr.t(f"error.{err.kind}", artifact=tr.t(f"artifact.{err.artifact}"))


def warning(text: str) -> None:
    st.warning(text, icon=":material/warning:")


def error_card(tr: Translator, err: ArtifactError) -> None:
    st.error(error_message(tr, err), icon=":material/error:")


def fatal_error(tr: Translator, err: ArtifactError) -> None:
    st.title(tr.t("error.title"))
    error_card(tr, err)


def snapshot(tr: Translator, issue_date: date) -> None:
    """Always-visible label: the forecast is a snapshot from the last observed day (Q5)."""
    info(tr.t("notice.snapshot", date=tr.date(issue_date)), icon="schedule")
