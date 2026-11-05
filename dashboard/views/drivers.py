"""Key Factors page views (scope §4.2)."""

import pandas as pd
import streamlit as st

from dashboard.models.artifacts import ArtifactError
from dashboard.models.drivers import HORIZONS, NEXT_DAY, POLLUTANT, SAME_DAY, WEATHER, Findings
from dashboard.models.forecast import ADVISORY_AQI, CALM_WIND_KMH, DRY_DAYS
from dashboard.views.components import charts, notices
from dashboard.views.components.download import csv_download
from dashboard.views.components.glossary import glossary
from dashboard.views.i18n import Translator


def _rho(tr: Translator, value: float) -> str:
    return tr.number(value, decimals=2)


def header(tr: Translator, f: Findings) -> None:
    """Title, the causation caveat, and the plain-language findings (NB §9.1, §9.5)."""
    st.title(tr.t("page.drivers"))
    notices.info(tr.t("drivers.caveat"), icon="lightbulb")
    st.subheader(tr.t("drivers.findings.heading"))
    bullets = [
        tr.t(
            "drivers.findings.pm",
            pm25_same=_rho(tr, f.pm25_same),
            pm25_next=_rho(tr, f.pm25_next),
            pm10_same=_rho(tr, f.pm10_same),
            o3_same=_rho(tr, f.o3_same),
        ),
        tr.t(
            "drivers.findings.rain",
            rain_same=_rho(tr, f.rain_hours_same),
            rain_next=_rho(tr, f.rain_hours_next),
        ),
        tr.t("drivers.findings.wind", wind_no2=_rho(tr, f.wind_no2), wind_co=_rho(tr, f.wind_co)),
        tr.t("drivers.findings.persistence", persistence=_rho(tr, f.persistence)),
    ]
    if f.top_features is not None:
        top1, top2, top3 = (tr.feature(name) for name in f.top_features)
        bullets.append(tr.t("drivers.findings.model", top1=top1, top2=top2, top3=top3))
    bullets.append(
        tr.t(
            "drivers.findings.warning",
            dry_days=DRY_DAYS,
            wind_kmh=CALM_WIND_KMH,
            threshold=ADVISORY_AQI,
        )
    )
    st.markdown("\n".join(f"- {text}" for text in bullets))


def horizon_toggle(tr: Translator) -> str:
    st.subheader(tr.t("drivers.correlation.heading"))
    st.caption(tr.t("drivers.correlation.caption"))
    glossary(tr, [("spearman", {"min": tr.number(-1, 0), "max": 1, "zero": 0})])
    return st.segmented_control(
        tr.t("drivers.horizon.label"),
        options=HORIZONS,
        format_func=lambda h: tr.t(f"drivers.horizon.{h}"),
        required=True,
        default=SAME_DAY,
        key="drv_horizon",
    )


def correlations(tr: Translator, ranking: pd.DataFrame, horizon: str) -> None:
    # Stacked at full width: long variable labels leave too little room for bars in columns.
    for group in (POLLUTANT, WEATHER):
        st.markdown(f"**{tr.t(f'drivers.group.{group}')}**")
        subset = ranking.loc[ranking["group"] == group]
        st.altair_chart(charts.correlation_chart(subset, tr, horizon), width="stretch")
    with st.expander(tr.t("drivers.correlation.table")):
        table = ranking.sort_values(SAME_DAY, ascending=False)
        st.table(
            pd.DataFrame(
                {
                    tr.t("drivers.variable"): table["variable"].map(tr.feature),
                    tr.t("drivers.horizon.same_day"): table[SAME_DAY].map(lambda v: _rho(tr, v)),
                    tr.t("drivers.horizon.next_day"): table[NEXT_DAY].map(lambda v: _rho(tr, v)),
                }
            ),
            hide_index=True,
            border="horizontal",
        )
        csv_download(
            tr,
            ranking.rename(columns={SAME_DAY: "spearman_same_day", NEXT_DAY: "spearman_next_day"}),
            "denpasar_spearman_correlations.csv",
            key="dl_spearman",
        )


def importance(tr: Translator, top: pd.DataFrame, *, excluded: int) -> None:
    st.subheader(tr.t("drivers.importance.heading"))
    st.caption(tr.t("drivers.importance.caption"))
    glossary(tr, [("importance", {})])
    st.altair_chart(charts.importance_chart(top, tr), width="stretch")
    if excluded:
        st.caption(tr.t("drivers.importance.excluded", count=excluded))


def importance_error(tr: Translator, err: ArtifactError) -> None:
    st.subheader(tr.t("drivers.importance.heading"))
    notices.error_card(tr, err)
