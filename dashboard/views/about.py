"""About page views (scope §4.4): where the numbers come from, how to read them, their limits."""

from html import escape

import pandas as pd
import streamlit as st

from aqi_forecasting.config import TREND_ROLLING_WINDOW, WHO_PM25_24H_GUIDELINE
from dashboard.models.artifacts import ArtifactError
from dashboard.models.forecast import ACTIONABLE_DAYS, ADVISORY_AQI
from dashboard.models.metadata import DataFacts, ModelFacts
from dashboard.views.components import notices
from dashboard.views.components.aqi_badge import badge_html
from dashboard.views.components.html_table import html_table
from dashboard.views.components.sources import sources_markdown
from dashboard.views.i18n import Translator


def _bullets(lines: list[str]) -> None:
    st.markdown("\n".join(f"- {line}" for line in lines))


def intro(tr: Translator) -> None:
    st.title(tr.t("page.about"))
    st.subheader(tr.t("about.intro.heading"))
    st.markdown(tr.t("about.intro.body"))
    _bullets([tr.t(f"about.intro.tool{i}") for i in (1, 2, 3)])


def data_section(tr: Translator, facts: DataFacts) -> None:
    st.subheader(tr.t("about.data.heading"))
    _bullets(
        [
            tr.t(
                "about.data.period",
                start=tr.date(facts.start),
                end=tr.date(facts.end),
                days=tr.number(facts.n_days, decimals=0),
            ),
            tr.t("about.data.estimates"),
            tr.t("about.data.version", version=facts.data_version),
        ]
    )
    st.markdown(sources_markdown(tr))

    st.subheader(tr.t("about.cams.heading"))
    _bullets(
        [tr.t("about.cams.upgrade", version=v, date=d) for v, d in facts.cams_upgrades.items()]
        + [tr.t("about.cams.why")]
    )


def aqi_section(tr: Translator, scale: pd.DataFrame) -> None:
    st.subheader(tr.t("about.aqi.heading"))
    st.markdown(tr.t("about.aqi.body"))
    rows = []
    for row in scale.itertuples():
        if pd.isna(row.upper):
            bounds = tr.t("about.aqi.from", lower=row.lower)
        else:
            bounds = f"{row.lower}–{int(row.upper)}"
        # Meaning under the badge in one cell, so the table keeps two columns on phones.
        category = (
            badge_html(tr, row.label, with_scale=False, wrap=True)
            + f'<div style="margin-top:0.3rem">{escape(tr.t(_meaning(row.label)))}</div>'
        )
        rows.append([bounds, category])
    html_table(
        [tr.t("about.aqi.range"), tr.t("about.aqi.category")],
        rows,
        raw_columns={1},
        css_class="aqi-legend",
    )
    st.caption(tr.t("about.aqi.source"))
    notices.info(tr.t("about.aqi.ispu"), icon="info")


def _meaning(label: str) -> str:
    return "about.aqi.meaning." + label.lower().replace(" ", "_")


def model_section(tr: Translator, facts: ModelFacts) -> None:
    st.subheader(tr.t("about.model.heading"))
    _bullets(
        [
            tr.t(
                "about.model.what",
                horizon=facts.horizon,
                features=facts.n_features,
            ),
            tr.t(
                "about.model.refit",
                rows=tr.number(facts.refit_rows, decimals=0),
                start=tr.date(facts.refit_start),
                end=tr.date(facts.refit_end),
            ),
            tr.t(
                "about.model.trees",
                trees=facts.n_estimators,
                depth=facts.max_depth,
                leaf=facts.min_samples_leaf,
            ),
            tr.t("about.model.band"),
        ]
    )


def model_error(tr: Translator, err: ArtifactError) -> None:
    st.subheader(tr.t("about.model.heading"))
    notices.error_card(tr, err)


def use_section(tr: Translator, horizon: int) -> None:
    st.subheader(tr.t("about.use.heading"))
    _bullets(
        [
            tr.t(
                "about.use.days",
                last=ACTIONABLE_DAYS,
                first_outlook=ACTIONABLE_DAYS + 1,
                horizon=horizon,
            ),
            tr.t("about.use.human"),
            tr.t("about.use.retrain"),
            tr.t("about.use.tiers", threshold=ADVISORY_AQI, days=ACTIONABLE_DAYS),
        ]
    )


def glossary_section(tr: Translator, horizon: int) -> None:
    """Every term explained elsewhere in the app, in one place."""
    st.subheader(tr.t("about.glossary.heading"))
    values = {
        "us_aqi": {"low": 0, "high": 300},
        "range": {"share": 8},
        "outlook": {
            "first": 1,
            "last": ACTIONABLE_DAYS,
            "outlook_first": ACTIONABLE_DAYS + 1,
            "horizon": horizon,
        },
        "sensitive": {},
        "pm25": {"size": tr.number(2.5)},
        "who": {"year": 2021, "limit": tr.number(WHO_PM25_24H_GUIDELINE, decimals=0)},
        "rolling": {"days": TREND_ROLLING_WINDOW},
        "cams": {},
        "spearman": {"min": tr.number(-1, 0), "max": 1, "zero": 0},
        "importance": {},
        "tiers": {"threshold": ADVISORY_AQI, "days": ACTIONABLE_DAYS},
        "accuracy": {},
        "rmse": {},
        "mae": {},
        "smape": {},
        "benchmarks": {},
    }
    _bullets([tr.t(f"glossary.{key}", **v) for key, v in values.items()])


def limits_section(tr: Translator, *, extreme_days: int, history_years: int) -> None:
    """Data and scope limitations (NB §9.6), with counts read from the data."""
    st.subheader(tr.t("about.limits.heading"))
    _bullets(
        [
            tr.t("about.limits.model_data", year=2023),
            tr.t("about.limits.history", years=history_years),
            tr.t("about.limits.weather"),
            tr.t("about.limits.extremes", days=extreme_days, threshold=ADVISORY_AQI),
            tr.t("about.limits.drivers"),
            tr.t("about.limits.band"),
        ]
    )
