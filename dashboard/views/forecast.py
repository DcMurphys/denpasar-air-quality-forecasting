"""7-Day Forecast page views (scope §4.3): forecast and Reliability sections."""

from collections.abc import Callable
from datetime import date
from html import escape

import pandas as pd
import streamlit as st

from aqi_forecasting.config import HORIZON
from dashboard.models.artifacts import ArtifactError
from dashboard.models.forecast import (
    ACTIONABLE_DAYS,
    ADVISORY_AQI,
    CALM_WIND_KMH,
    DRY_DAYS,
    HISTORY_WINDOWS,
    NO_RAIN_MM,
    SHORT_HISTORY_DAYS,
    Advisory,
    relative_day,
)
from dashboard.models.performance import BENCHMARKS, MODEL, Scorecard
from dashboard.views.components import charts, notices
from dashboard.views.components.aqi_badge import badge_html
from dashboard.views.components.download import csv_download
from dashboard.views.components.glossary import glossary
from dashboard.views.components.html_table import html_table
from dashboard.views.components.palette import MUTED_TEXT
from dashboard.views.i18n import Translator


def header(tr: Translator, issue_date: date) -> None:
    """Title, the always-visible snapshot label (Q5), and the supervised-use notice (NB §7.10)."""
    st.title(tr.t("page.forecast"))
    notices.snapshot(tr, issue_date)
    notices.info(
        tr.t(
            "forecast.supervised",
            actionable_days=ACTIONABLE_DAYS,
            first_outlook=ACTIONABLE_DAYS + 1,
            horizon=HORIZON,
        ),
        icon="supervisor_account",
    )


def forecast_error(tr: Translator, err: ArtifactError) -> None:
    notices.error_card(tr, err)


def advisory_panel(tr: Translator, adv: Advisory, last_date: date) -> None:
    """Indicative Tier 1 / Tier 2 status (NB §9.5) with the conditions behind it."""
    st.subheader(tr.t("forecast.advisory.heading"))
    days = ", ".join(str(d) for d in adv.trigger_days)
    if adv.level == "tier2":
        st.error(
            tr.t("forecast.advisory.tier2", days=days, threshold=ADVISORY_AQI),
            icon=":material/emergency_home:",
        )
    elif adv.level == "tier1":
        st.warning(
            tr.t("forecast.advisory.tier1", days=days, threshold=ADVISORY_AQI),
            icon=":material/warning:",
        )
    else:
        # Green "good" status, not the red-tinted info callout: a safe state must not look alarming.
        st.success(
            tr.t(
                "forecast.advisory.none",
                actionable_days=ACTIONABLE_DAYS,
                max_high=tr.number(adv.max_high),
                threshold=ADVISORY_AQI,
            ),
            icon=":material/check_circle:",
        )
    met, unmet = tr.t("forecast.advisory.met"), tr.t("forecast.advisory.unmet")
    st.caption(
        tr.t(
            "forecast.advisory.conditions",
            date=tr.date(last_date),
            dry_days=DRY_DAYS,
            rain=tr.number(adv.max_recent_rain),
            no_rain=tr.number(NO_RAIN_MM, decimals=0),
            dry_status=met if adv.dry else unmet,
            wind=tr.number(adv.last_wind),
            calm=CALM_WIND_KMH,
            calm_status=met if adv.calm else unmet,
        )
    )


def history_window(tr: Translator) -> int:
    """Days of observed history shown before the forecast (14 by default, 60 as in the NB)."""
    st.subheader(tr.t("forecast.chart.heading"))
    return st.segmented_control(
        tr.t("forecast.history.label"),
        options=HISTORY_WINDOWS,
        format_func=lambda days: tr.t("forecast.history.days", days=days),
        required=True,
        default=SHORT_HISTORY_DAYS,
        key="fc_history",
    )


def forecast_chart(
    tr: Translator, history: pd.DataFrame, forecast: pd.DataFrame, today: date
) -> None:
    st.caption(tr.t("forecast.chart.caption", days=len(history)))
    glossary(
        tr,
        [
            ("range", {"share": 8}),
            (
                "outlook",
                {
                    "first": 1,
                    "last": ACTIONABLE_DAYS,
                    "outlook_first": ACTIONABLE_DAYS + 1,
                    "horizon": HORIZON,
                },
            ),
            ("tiers", {"threshold": ADVISORY_AQI, "days": ACTIONABLE_DAYS}),
        ],
    )
    st.altair_chart(
        charts.forecast_chart(history, forecast, tr, ACTIONABLE_DAYS, today=today), width="stretch"
    )


def _date_cell(tr: Translator, day: date, horizon: int, today: date) -> str:
    """Date with the forecast day and its relation to today underneath (fits on phones)."""
    note = escape(tr.t("forecast.table.day_n", day=horizon))
    relation = relative_day(day, today)
    if relation != "later":
        tag = escape(tr.t(f"forecast.table.{relation}"))
        note += f" · <strong>{tag}</strong>" if relation != "past" else f" · {tag}"
    style = f"font-size:0.85rem;color:{MUTED_TEXT}"
    return f'{escape(tr.date(day))}<br><span style="{style}">{note}</span>'


def forecast_tables(tr: Translator, forecast: pd.DataFrame, today: date) -> None:
    """The 7 days in two groups: actionable (1-3) and outlook (4-7)."""
    columns = [
        tr.t("chart.date"),
        tr.t("forecast.table.forecast"),
        tr.t("forecast.table.band"),
        tr.t("forecast.table.category_scale"),
    ]
    groups = (
        ("actionable", forecast["horizon"] <= ACTIONABLE_DAYS, 1, ACTIONABLE_DAYS),
        ("outlook", forecast["horizon"] > ACTIONABLE_DAYS, ACTIONABLE_DAYS + 1, HORIZON),
    )
    for key, mask, first, last in groups:
        group = forecast.loc[mask]
        rows = [
            [
                _date_cell(tr, row.date, row.horizon, today),
                tr.number(row.aqi_pred),
                f"{tr.number(row.aqi_low)} – {tr.number(row.aqi_high)}",
                badge_html(tr, str(row.category), with_scale=False),
            ]
            for row in group.itertuples()
        ]
        html_table(
            columns,
            rows,
            raw_columns={0, 3},
            css_class=f"forecast-table forecast-{key}",
            caption=tr.t(f"forecast.group.{key}", first=first, last=last),
            highlight_rows=frozenset(
                i for i, d in enumerate(group["date"]) if relative_day(d.date(), today) == "today"
            ),
        )
    csv_download(
        tr,
        forecast.assign(category=forecast["category"].astype(str)),
        f"denpasar_forecast_{forecast['date'].min().date()}.csv",
        key="dl_forecast",
    )


# ===== Reliability (scope §4.3, M10) =====
def _status(tr: Translator, met: bool) -> str:
    icon = ":material/check_circle:" if met else ":material/cancel:"
    return f"{icon} **{tr.t('reliability.met' if met else 'reliability.unmet')}**"


def reliability(
    tr: Translator,
    *,
    card: Scorecard,
    per_h: pd.DataFrame,
    table: pd.DataFrame,
    regime: pd.DataFrame,
    test_bounds: list[str],
    avp_for: Callable[[int], pd.DataFrame],
    cams_50r1: str,
) -> None:
    """How far the forecast can be trusted, on the held-out test period only."""
    st.subheader(tr.t("reliability.heading"))
    st.caption(tr.t("reliability.caption", start=test_bounds[0], end=test_bounds[1]))

    model = per_h.xs(MODEL, level="model")["Category accuracy (%)"]
    near, far = model.loc[:ACTIONABLE_DAYS], model.loc[ACTIONABLE_DAYS + 1 :]
    notices.info(
        tr.t(
            "reliability.summary",
            last=ACTIONABLE_DAYS,
            near_low=tr.percent(near.min(), 0),
            near_high=tr.percent(near.max(), 0),
            first_outlook=ACTIONABLE_DAYS + 1,
            far_low=tr.percent(far.min(), 0),
            far_high=tr.percent(far.max(), 0),
        ),
        icon="fact_check",
    )

    st.markdown(f"**{tr.t('reliability.scorecard')}**")
    st.markdown(
        "\n".join(
            [
                "- "
                + _status(tr, card.b3_met)
                + " · "
                + tr.t(
                    "reliability.b3",
                    model=tr.percent(card.model_accuracy, 2),
                    bench=tr.percent(card.best_benchmark_accuracy, 2),
                ),
                "- "
                + _status(tr, card.d4_met)
                + " · "
                + tr.t(
                    "reliability.d4",
                    rmse=tr.number(card.model_rmse, 2),
                    bench_rmse=tr.number(card.best_benchmark_rmse, 2),
                    mae=tr.number(card.model_mae, 2),
                    bench_mae=tr.number(card.best_benchmark_mae, 2),
                ),
                "- "
                + _status(tr, card.d5_met)
                + " · "
                + tr.t(
                    "reliability.d5",
                    smape=tr.percent(card.model_smape, 2),
                    target=tr.percent(card.smape_target, 0),
                    day1=tr.percent(card.day1_smape, 2),
                ),
            ]
        )
    )

    accuracy = model.rename("accuracy").reset_index()
    best_bench = float(table.loc[list(BENCHMARKS), "Category accuracy (%)"].max())
    st.altair_chart(
        charts.horizon_accuracy_chart(accuracy, tr, ACTIONABLE_DAYS, best_bench), width="stretch"
    )
    st.caption(tr.t("reliability.benchmark_line", value=tr.percent(best_bench, 2)))
    glossary(
        tr,
        [
            ("accuracy", {}),
            ("rmse", {}),
            ("mae", {}),
            ("smape", {}),
            ("benchmarks", {}),
        ],
    )

    with st.expander(tr.t("reliability.details"), icon=":material/analytics:"):
        st.markdown(f"**{tr.t('reliability.benchmark_table')}**")
        html_table(
            [
                tr.t("reliability.model_col"),
                "RMSE",
                "MAE",
                "sMAPE",
                tr.t("reliability.accuracy"),
            ],
            [
                [
                    tr.t(f"reliability.model.{name}"),
                    tr.number(row["RMSE"], 2),
                    tr.number(row["MAE"], 2),
                    tr.percent(row["sMAPE (%)"], 2),
                    tr.percent(row["Category accuracy (%)"], 2),
                ]
                for name, row in table.iterrows()
            ],
            css_class="benchmark-table",
        )
        st.markdown(f"**{tr.t('reliability.rmse_heading')}**")
        st.altair_chart(
            charts.rmse_by_horizon_chart(per_h, tr, [MODEL, *BENCHMARKS]), width="stretch"
        )
        st.markdown(f"**{tr.t('reliability.regime_heading')}**")
        st.caption(tr.t("reliability.regime_caption", date=cams_50r1))
        html_table(
            [
                tr.t("forecast.table.day"),
                tr.t("reliability.regime_before"),
                tr.t("reliability.regime_after"),
            ],
            [
                [
                    str(int(row.horizon)),
                    f"{tr.number(row.before, 2)} (n = {int(row.n_before)})",
                    f"{tr.number(row.after, 2)} (n = {int(row.n_after)})",
                ]
                for row in regime.itertuples()
            ],
            css_class="regime-table",
        )
        st.markdown(f"**{tr.t('reliability.avp_heading')}**")
        horizon = st.segmented_control(
            tr.t("forecast.table.day"),
            options=list(range(1, HORIZON + 1)),
            format_func=lambda h: tr.t("forecast.table.day_n", day=h),
            required=True,
            default=1,
            key="fc_avp_horizon",
        )
        st.altair_chart(
            charts.actual_vs_predicted_chart(avp_for(horizon), tr, cams_50r1), width="stretch"
        )


def reliability_error(tr: Translator, err: ArtifactError) -> None:
    st.subheader(tr.t("reliability.heading"))
    notices.error_card(tr, err)
