"""Overview page views (scope §4.1)."""

from collections.abc import Callable
from datetime import date

import pandas as pd
import streamlit as st

from aqi_forecasting.config import (
    HORIZON,
    TARGET,
    TREND_ROLLING_WINDOW,
    WHO_PM25_24H_GUIDELINE,
)
from dashboard.models.artifacts import ArtifactError
from dashboard.models.baseline import (
    ALL_SEASONS,
    SEASONS,
    TREND_VARIABLES,
    UNHEALTHY_THRESHOLD,
    CurrentStatus,
    YearRange,
)
from dashboard.models.forecast import ACTIONABLE_DAYS, DayOutlook
from dashboard.views.components import charts, notices
from dashboard.views.components.aqi_badge import badge_html
from dashboard.views.components.day_card import day_cards
from dashboard.views.components.download import csv_download
from dashboard.views.components.glossary import glossary
from dashboard.views.components.kpi_card import Kpi, kpi_grid
from dashboard.views.i18n import Translator


def today_block(
    tr: Translator,
    *,
    today: DayOutlook,
    tomorrow: DayOutlook,
    last_date: date,
    age_days: int,
    forecast_error: ArtifactError | None,
    forecast_page,
) -> None:
    """Page title, then "today" and "tomorrow" first: what most visitors come for."""
    st.title(tr.t("page.overview"))
    st.subheader(tr.t("today.heading"))
    if age_days >= 2:
        notices.warning(tr.t("today.age.stale", date=tr.date(last_date), days=age_days))
    else:
        notices.info(tr.t("today.age.fresh", date=tr.date(last_date)), icon="schedule")
    if forecast_error is not None:
        notices.error_card(tr, forecast_error)
    day_cards(
        tr,
        [
            (tr.t("today.card.today", date=tr.date(today.day)), today),
            (tr.t("today.card.tomorrow", date=tr.date(tomorrow.day)), tomorrow),
        ],
    )
    st.caption(tr.t("advice.groups"))
    st.caption(tr.t("advice.source"))
    glossary(
        tr,
        [
            ("us_aqi", {"low": 0, "high": 300}),
            ("range", {"share": 8}),
            ("outlook", _outlook_values()),
            ("sensitive", {}),
        ],
    )
    st.page_link(forecast_page, label=tr.t("overview.next3.link"), icon=":material/arrow_forward:")


def _outlook_values() -> dict:
    return {
        "first": 1,
        "last": ACTIONABLE_DAYS,
        "outlook_first": ACTIONABLE_DAYS + 1,
        "horizon": HORIZON,
    }


def current_status(tr: Translator, status: CurrentStatus) -> None:
    """Summary KPI cards over the whole period (not affected by the history filters)."""
    st.subheader(tr.t("overview.status.heading"))

    kpis = [
        Kpi(
            tr.t("overview.kpi.latest_aqi", date=tr.date(status.latest_date)),
            tr.number(status.latest_aqi),
            icon="air",
            extra_html=badge_html(tr, status.latest_category),
        ),
        Kpi(tr.t("overview.kpi.mean_aqi"), tr.number(status.mean_aqi), icon="monitoring"),
        Kpi(
            tr.t("overview.kpi.days_above_100", threshold=UNHEALTHY_THRESHOLD),
            tr.t(
                "overview.kpi.count_of_total",
                count=tr.number(status.days_above_100, decimals=0),
                total=tr.number(status.n_days, decimals=0),
                share=tr.percent(status.share_above_100),
            ),
            icon="warning",
        ),
        Kpi(
            tr.t("overview.kpi.dry_wet"),
            f"{tr.number(status.dry_mean)} / {tr.number(status.wet_mean)}",
            icon="partly_cloudy_day",
        ),
        Kpi(
            tr.t("overview.kpi.mean_pm25"),
            tr.t("unit.ugm3", value=tr.number(status.mean_pm25)),
            icon="grain",
        ),
    ]
    if status.who_share is not None:
        limit = tr.number(WHO_PM25_24H_GUIDELINE, decimals=0)
        kpis.append(
            Kpi(
                tr.t("overview.kpi.who_share", limit=limit),
                tr.percent(status.who_share),
                icon="health_and_safety",
            )
        )
    kpi_grid(kpis)
    glossary(
        tr,
        [
            ("pm25", {"size": tr.number(2.5)}),
            ("who", {"year": 2021, "limit": tr.number(WHO_PM25_24H_GUIDELINE, decimals=0)}),
        ],
    )
    if status.who_share is None:
        notices.warning(tr.t("warning.who_flag"))


# ===== History: filters and tabs (scope §4.1) =====
def history_filters(tr: Translator, bounds: YearRange) -> tuple[YearRange, str]:
    """Year-range and season filters shared by the four tabs; returns the selected values."""
    st.subheader(tr.t("overview.history.heading"))
    with st.container(horizontal=True, vertical_alignment="bottom", gap="medium"):
        years = st.slider(
            tr.t("overview.filters.years"),
            min_value=bounds[0],
            max_value=bounds[1],
            value=bounds,
            step=1,
            key="ov_years",
            width=360,
        )
        season = st.segmented_control(
            tr.t("overview.filters.season"),
            options=SEASONS,
            format_func=lambda s: tr.t("season.all") if s == ALL_SEASONS else tr.season(s),
            required=True,
            default=ALL_SEASONS,
            key="ov_season",
        )
    return (int(years[0]), int(years[1])), season


def _trend_controls(tr: Translator, date_range: tuple[date, date]) -> tuple[str, tuple[date, date]]:
    """Variable and date-range pickers for experts (UX priority 8), inside the Trend tab."""
    with st.container(horizontal=True, vertical_alignment="bottom", gap="medium"):
        variable = st.selectbox(
            tr.t("overview.trend.variable"),
            options=TREND_VARIABLES,
            format_func=tr.feature,
            key="ov_trend_var",
            width=320,
        )
        # The key follows the year filter, so the picker resets to the new bounds.
        picked = st.date_input(
            tr.t("overview.trend.dates"),
            value=date_range,
            min_value=date_range[0],
            max_value=date_range[1],
            format="YYYY-MM-DD",
            key=f"ov_trend_dates_{date_range[0]}_{date_range[1]}",
            width=260,
        )
    # While a range is being picked, the widget briefly returns a single date.
    dates = tuple(picked) if isinstance(picked, (tuple, list)) and len(picked) == 2 else date_range
    return variable, dates


def _signed_percent(tr: Translator, value: float) -> str:
    if pd.isna(value):
        return "–"
    sign = "+" if value > 0 else ""
    return sign + tr.percent(value, decimals=2)


def history_tabs(
    tr: Translator,
    *,
    annual: pd.DataFrame,
    trend_for: Callable[[str, tuple[date, date]], pd.DataFrame],
    date_range: tuple[date, date],
    profile: pd.DataFrame,
    seasons: pd.DataFrame,
    unhealthy: pd.DataFrame,
    all_years: list[int],
    cams: dict[str, str],
) -> None:
    trend_tab, annual_tab, season_tab, unhealthy_tab = st.tabs(
        [
            tr.t("overview.tab.trend"),
            tr.t("overview.tab.annual"),
            tr.t("overview.tab.seasonality"),
            tr.t("overview.tab.unhealthy"),
        ]
    )
    with trend_tab:
        variable, dates = _trend_controls(tr, date_range)
        if variable == TARGET:
            st.caption(tr.t("overview.trend.caption"))
        else:
            st.caption(tr.t("overview.trend.caption_variable", variable=tr.feature(variable)))
        glossary(tr, [("rolling", {"days": TREND_ROLLING_WINDOW}), ("cams", {})])
        trend = trend_for(variable, dates)
        st.altair_chart(charts.trend_chart(trend, tr, cams, variable), width="stretch")
        csv_download(
            tr,
            trend.drop(columns="segment").rename(
                columns={"value": variable, "rolling_mean": f"{variable}_rolling_mean_30d"}
            ),
            f"denpasar_{variable}_{dates[0]}_{dates[1]}.csv",
            key="dl_trend",
        )
    with annual_tab:
        st.caption(tr.t("overview.annual.caption"))
        threshold = UNHEALTHY_THRESHOLD
        table = pd.DataFrame(
            {
                # Partial years are starred in the year cell (explained in the caption), so the
                # mark stays visible on a 375 px screen without a separate column.
                tr.t("overview.annual.year"): [
                    f"{year}*" if partial else str(year)
                    for year, partial in zip(annual["year"], annual["partial"], strict=True)
                ],
                tr.t("overview.annual.days"): annual["days"].map(
                    lambda n: tr.number(n, decimals=0)
                ),
                tr.t("overview.annual.mean"): annual["mean_aqi"].map(
                    lambda v: tr.number(v, decimals=2)
                ),
                tr.t("overview.annual.share_above", threshold=threshold): annual[
                    "pct_days_above_100"
                ].map(lambda v: tr.percent(v, decimals=2)),
                tr.t("overview.annual.yoy"): annual["yoy_change_pct"].map(
                    lambda v: _signed_percent(tr, v)
                ),
            }
        )
        st.table(table, hide_index=True, border="horizontal")
        csv_download(tr, annual, "denpasar_annual_kpis.csv", key="dl_annual")
    with season_tab:
        st.caption(tr.t("overview.season.caption"))
        st.altair_chart(charts.monthly_profile_chart(profile, tr, all_years), width="stretch")
        with st.expander(tr.t("overview.season.table")):
            pivot = profile.pivot(index="month", columns="year", values="mean_aqi")
            pivot = pivot.map(lambda v: tr.number(v) if pd.notna(v) else "–")
            pivot.index = [tr.month(m) for m in pivot.index]  # short names fit phones
            pivot.columns = [str(c) for c in pivot.columns]
            st.table(pivot.rename_axis(tr.t("chart.month")), border="horizontal")
        st.markdown(f"**{tr.t('overview.season.compare')}**")
        st.altair_chart(charts.season_chart(seasons, tr), width="stretch")
    with unhealthy_tab:
        st.caption(tr.t("overview.unhealthy.caption", threshold=UNHEALTHY_THRESHOLD))
        if unhealthy.empty:
            notices.info(tr.t("overview.unhealthy.none", threshold=UNHEALTHY_THRESHOLD))
        else:
            st.table(
                pd.DataFrame(
                    {
                        tr.t("chart.date"): unhealthy["date"].map(tr.date),
                        tr.t("chart.aqi"): unhealthy["aqi"].map(tr.number),
                        tr.t("overview.unhealthy.category"): unhealthy["category"].map(tr.category),
                    }
                ),
                hide_index=True,
                border="horizontal",
            )
