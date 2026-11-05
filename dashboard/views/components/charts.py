"""Altair chart builders (scope §6). Text is translated and numbers are pre-formatted.

Mark specs follow the dataviz guidance: thin 2 px lines, recessive grid, a legend for two or
more series, hover tooltips, and categorical colours in a fixed, validated order.
"""

from datetime import date

import altair as alt
import pandas as pd

from aqi_forecasting.config import AQI_CATEGORIES, TARGET, TREND_ROLLING_WINDOW
from dashboard.views.components.palette import BLACK, MUTED_TEXT
from dashboard.views.components.palette import RED as RED_ACCENT
from dashboard.views.i18n import Translator

# Categorical slots 1-5 of the reference palette, validated on white (CVD ΔE 9.1, normal ΔE
# 19.6). Three slots sit below 3:1 contrast, so every chart using them has a legend and a
# table view. Colours follow the entity (year), never its rank.
YEAR_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
DAILY_GRAY = "#9a9a9a"
GRID = "#e6e6e6"
CHART_HEIGHT = 320
# With a fallback, so charts never render in the browser's default serif before Inter loads.
CHART_FONT = "Inter, sans-serif"
# Minimum chart text sizes (UX review, priority 3): axis/value labels 13 px, titles 14 px.
CHART_TEXT_SIZE = 13
CHART_TITLE_SIZE = 14


def _silence_raw_tooltips(chart: alt.TopLevelMixin) -> None:
    """Turn off the tooltip of every layer that has no tooltip encoding of its own.

    Streamlit shows a default tooltip with the raw encoded fields (e.g. ``lower``, ``upper``,
    and a hex colour on the category bands), which means nothing to a lay reader. Only the
    layers with translated, formatted tooltips keep one.
    """
    for layer in getattr(chart, "layer", None) or []:
        _silence_raw_tooltips(layer)
    if not isinstance(chart, alt.Chart):
        return
    encoding = chart.encoding
    if encoding is not alt.Undefined and encoding.tooltip is not alt.Undefined:
        return
    mark = chart.mark
    if isinstance(mark, str):
        chart.mark = alt.MarkDef(type=mark, tooltip=None)
    else:
        mark.tooltip = None


def _configure(chart: alt.TopLevelMixin) -> alt.TopLevelMixin:
    _silence_raw_tooltips(chart)
    return (
        chart.configure(font=CHART_FONT)
        .configure_axis(
            gridColor=GRID,
            domainColor=GRID,
            tickColor=GRID,
            labelColor=MUTED_TEXT,
            titleColor=MUTED_TEXT,
            labelFont=CHART_FONT,
            titleFont=CHART_FONT,
            titleFontWeight=500,
            labelFontSize=CHART_TEXT_SIZE,
            titleFontSize=CHART_TITLE_SIZE,
        )
        .configure_legend(
            orient="top",
            labelColor=BLACK,
            titleColor=MUTED_TEXT,
            labelFont=CHART_FONT,
            titleFont=CHART_FONT,
            labelLimit=0,  # never truncate translated series names
            labelFontSize=CHART_TEXT_SIZE,
            titleFontSize=CHART_TEXT_SIZE,
        )
        .configure_text(fontSize=CHART_TEXT_SIZE)
        .configure_view(strokeWidth=0)
    )


BAND_STRENGTH = 0.12  # category bands look like 12 % of the EPA colour over white


def _tint(hex_color: str, strength: float) -> str:
    """Blend a colour with white. Opaque tints avoid mark ``opacity``, which Vega-Lite would
    copy onto the legend symbols of the other layers and make them nearly invisible."""
    rgb = [int(hex_color[i : i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(255 - (255 - c) * strength) for c in rgb]
    return "#" + "".join(f"{c:02x}" for c in mixed)


def _category_bands(tr: Translator, y_max: float) -> alt.LayerChart:
    """Pale US AQI category bands up to ``y_max``, each labelled with its translated name."""
    rows, lower = [], 0.0
    for label, upper, color in AQI_CATEGORIES:
        if lower >= y_max:
            break
        top = min(upper, y_max)
        # Daily AQI mostly sits around 50, so the lowest band is labelled near its bottom
        # instead of its top, where the data line would cover the label.
        label_y = lower + (top - lower) * 0.35 if lower == 0 else top
        rows.append(
            {
                "lower": lower,
                "upper": top,
                "label_y": label_y,
                "color": _tint(color, BAND_STRENGTH),
                "name": tr.category(label),
            }
        )
        lower = upper
    bands = pd.DataFrame(rows)
    rect = (
        alt.Chart(bands)
        .mark_rect()
        .encode(y="lower:Q", y2="upper:Q", color=alt.Color("color:N", scale=None))
    )
    text = (
        alt.Chart(bands)
        .mark_text(
            align="left", baseline="top", dx=6, dy=4, fontSize=CHART_TEXT_SIZE, color=MUTED_TEXT
        )
        .encode(y="label_y:Q", text="name:N", x=alt.value(0))
    )
    return rect + text


def trend_chart(
    frame: pd.DataFrame, tr: Translator, cams: dict[str, str], variable: str = TARGET
) -> alt.TopLevelMixin:
    """Daily values of ``variable`` and their rolling mean, with CAMS upgrade markers.

    ``frame`` comes from ``models.baseline.trend``; ``cams`` maps version -> ISO date. US AQI
    category bands are drawn only when ``variable`` is the AQI.
    """
    is_aqi = variable == TARGET
    daily_name = tr.t("chart.daily") if is_aqi else tr.t("chart.daily_value")
    rolling_name = tr.t("chart.rolling", days=TREND_ROLLING_WINDOW)
    data = frame.assign(
        date_label=frame["date"].map(tr.date),
        aqi_label=frame["value"].map(tr.number),
        rolling_label=frame["rolling_mean"].map(lambda v: tr.number(v) if pd.notna(v) else "–"),
    )
    long = data.melt(
        id_vars=["date", "segment", "date_label", "aqi_label", "rolling_label"],
        value_vars=["value", "rolling_mean"],
        var_name="series_key",
        value_name="y",
    ).assign(
        series=lambda d: d["series_key"].map({"value": daily_name, "rolling_mean": rolling_name})
    )

    peak = float(frame["value"].max()) if len(frame) else 0.0
    y_max = max(150.0, peak * 1.05) if is_aqi else max(peak * 1.05, 1.0)
    x = alt.X("date:T", title=tr.t("chart.date"), axis=alt.Axis(format="%Y-%m", labelAngle=0))
    y_title = tr.t("chart.aqi") if is_aqi else tr.feature(variable)
    y = alt.Y("y:Q", title=y_title, scale=alt.Scale(domain=[0, y_max]))
    lines = (
        alt.Chart(long)
        .mark_line(strokeWidth=2, strokeJoin="round")
        .encode(
            x=x,
            y=y,
            detail="segment:N",
            color=alt.Color(
                "series:N",
                title=None,
                scale=alt.Scale(domain=[daily_name, rolling_name], range=[DAILY_GRAY, BLACK]),
                legend=alt.Legend(symbolType="stroke", symbolStrokeWidth=3, symbolOpacity=1),
            ),
            strokeWidth=alt.StrokeWidth(
                "series:N",
                legend=None,
                scale=alt.Scale(domain=[daily_name, rolling_name], range=[1, 2.5]),
            ),
        )
    )

    hover = alt.selection_point(fields=["date"], nearest=True, on="pointerover", empty=False)
    tooltip = [
        alt.Tooltip("date_label:N", title=tr.t("chart.date")),
        alt.Tooltip("aqi_label:N", title=daily_name),
        alt.Tooltip("rolling_label:N", title=rolling_name),
    ]
    catcher = (
        alt.Chart(data)
        .mark_rule(opacity=0, strokeWidth=12)
        .encode(x="date:T", tooltip=tooltip)
        .add_params(hover)
    )
    crosshair = (
        alt.Chart(data)
        .mark_rule(color=MUTED_TEXT, strokeWidth=1)
        .encode(x="date:T")
        .transform_filter(hover)
    )

    markers = pd.DataFrame(
        [
            {
                "date": pd.Timestamp(day),
                "label": f"CAMS {version}",
                "note": tr.t("chart.cams", version=version),
                "date_label": day,
            }
            for version, day in cams.items()
        ]
    )
    markers = (
        markers.loc[markers["date"].between(frame["date"].min(), frame["date"].max())]
        if len(frame)
        else markers.iloc[0:0]
    )
    cams_tooltip = [
        alt.Tooltip("date_label:N", title=tr.t("chart.date")),
        alt.Tooltip("note:N", title="CAMS"),
    ]
    cams_rules = (
        alt.Chart(markers)
        .mark_rule(color=BLACK, strokeDash=[4, 4], strokeWidth=1)
        .encode(x="date:T", tooltip=cams_tooltip)
    )
    cams_labels = (
        alt.Chart(markers)
        .mark_text(align="left", dx=4, dy=-6, fontSize=CHART_TEXT_SIZE, color=BLACK)
        .encode(x="date:T", y=alt.value(0), text="label:N", tooltip=cams_tooltip)
    )

    layers = [lines, crosshair, cams_rules, cams_labels, catcher]
    if is_aqi:
        layers.insert(0, _category_bands(tr, y_max))
    chart = alt.layer(*layers).properties(height=CHART_HEIGHT)
    return _configure(chart)


def monthly_profile_chart(
    profile: pd.DataFrame, tr: Translator, all_years: list[int]
) -> alt.TopLevelMixin:
    """One line per year over Jan-Dec; colours are fixed per year across filters."""
    months = [tr.month(m) for m in range(1, 13)]
    data = profile.assign(
        month_label=profile["month"].map(tr.month),
        year_label=profile["year"].astype(str),
        value_label=profile["mean_aqi"].map(tr.number),
    )
    color = alt.Color(
        "year_label:N",
        title=tr.t("chart.year"),
        scale=alt.Scale(domain=[str(y) for y in all_years], range=YEAR_COLORS[: len(all_years)]),
        # A 3-column grid wraps on phones instead of clipping the last years.
        legend=alt.Legend(columns=3),
    )
    tooltip = [
        alt.Tooltip("year_label:N", title=tr.t("chart.year")),
        alt.Tooltip("month_label:N", title=tr.t("chart.month")),
        alt.Tooltip("value_label:N", title=tr.t("chart.mean_aqi")),
    ]
    base = alt.Chart(data).encode(
        x=alt.X(
            "month_label:N", sort=months, title=tr.t("chart.month"), axis=alt.Axis(labelAngle=0)
        ),
        y=alt.Y("mean_aqi:Q", title=tr.t("chart.mean_aqi"), scale=alt.Scale(zero=False)),
        color=color,
        tooltip=tooltip,
    )
    lines = base.mark_line(strokeWidth=2)
    points = base.mark_point(size=64, filled=True, stroke="white", strokeWidth=2)
    return _configure((lines + points).properties(height=CHART_HEIGHT))


def season_chart(seasons: pd.DataFrame, tr: Translator) -> alt.TopLevelMixin:
    """Horizontal bars of mean AQI per season, each with a direct value label."""
    data = seasons.assign(
        season_label=seasons["season"].map(tr.season),
        value_label=seasons["mean_aqi"].map(tr.number),
        days_label=seasons["days"].map(lambda n: tr.number(n, decimals=0)),
    )
    tooltip = [
        alt.Tooltip("season_label:N", title=tr.t("chart.season")),
        alt.Tooltip("value_label:N", title=tr.t("chart.mean_aqi")),
        alt.Tooltip("days_label:N", title=tr.t("chart.days")),
    ]
    base = alt.Chart(data).encode(
        y=alt.Y("season_label:N", title=None, sort=None, scale=alt.Scale(paddingInner=0.4)),
        x=alt.X("mean_aqi:Q", title=tr.t("chart.mean_aqi"), scale=alt.Scale(domain=[0, 100])),
        tooltip=tooltip,
    )
    bars = base.mark_bar(color=BLACK, cornerRadiusEnd=4)
    labels = base.mark_text(align="left", dx=6, color=BLACK, fontWeight=600).encode(
        text="value_label:N"
    )
    return _configure((bars + labels).properties(height=130))


# ===== Key factors (scope §4.2) =====
# Diverging pair (dataviz reference: blue <-> red), validated on white: CVD ΔE 26.3, both >= 3:1.
POSITIVE_RED = "#D7192D"
NEGATIVE_BLUE = "#2a78d6"
AXIS_LABEL_LIMIT = 230
# Streamlit treats a chart's height as its total height (legend and axes included), so the
# bar charts reserve room for the x-axis on top of ~28 px per bar.
ROW_HEIGHT = 28
AXIS_ONLY = 70


def correlation_chart(ranking: pd.DataFrame, tr: Translator, horizon: str) -> alt.TopLevelMixin:
    """Spearman ρ per variable on a -1..1 axis; colour shows the direction of the link."""
    positive, negative = tr.t("drivers.legend.positive"), tr.t("drivers.legend.negative")
    data = (
        ranking.assign(
            rho=ranking[horizon],
            label=ranking["variable"].map(tr.feature),
            direction=lambda d: d["rho"].map(lambda v: positive if v >= 0 else negative),
            rho_label=lambda d: d["rho"].map(lambda v: ("+" if v > 0 else "") + tr.number(v, 2)),
        )
        .sort_values("rho", ascending=False)
        .reset_index(drop=True)
    )
    order = data["label"].tolist()
    tooltip = [
        alt.Tooltip("label:N", title=tr.t("drivers.variable")),
        alt.Tooltip("rho_label:N", title=tr.t("drivers.rho")),
    ]
    y = alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=AXIS_LABEL_LIMIT))
    x = alt.X("rho:Q", title=tr.t("drivers.rho"), scale=alt.Scale(domain=[-1, 1]))
    base = alt.Chart(data).encode(y=y, tooltip=tooltip)
    bars = base.mark_bar(cornerRadiusEnd=4).encode(
        x=x,
        color=alt.Color(
            "direction:N",
            title=None,
            scale=alt.Scale(domain=[positive, negative], range=[POSITIVE_RED, NEGATIVE_BLUE]),
            # No legend: it does not fit on phones, and every bar carries a signed value label
            # while the caption above explains red/blue, so direction is never colour-only.
            legend=None,
        ),
    )
    right = base.transform_filter("datum.rho >= 0").mark_text(align="left", dx=4, color=BLACK)
    left = base.transform_filter("datum.rho < 0").mark_text(align="right", dx=-4, color=BLACK)
    labels = right.encode(x="rho:Q", text="rho_label:N") + left.encode(
        x="rho:Q", text="rho_label:N"
    )
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=MUTED_TEXT).encode(x="x:Q")
    height = ROW_HEIGHT * len(data) + AXIS_ONLY
    chart = alt.layer(bars, labels, zero).properties(height=height)
    return _configure(chart.configure_scale(bandPaddingInner=0.3))


def importance_chart(top: pd.DataFrame, tr: Translator) -> alt.TopLevelMixin:
    """Top features by permutation importance, with ±1 standard-deviation error bars."""
    data = top.assign(
        label=top["feature"].map(tr.feature),
        low=(top["importance"] - top["std"]).clip(lower=0),
        high=top["importance"] + top["std"],
        value_label=top["importance"].map(lambda v: tr.number(v, 2)),
        std_label=top["std"].map(lambda v: tr.number(v, 2)),
    )
    order = data["label"].tolist()
    tooltip = [
        alt.Tooltip("label:N", title=tr.t("drivers.feature")),
        alt.Tooltip("value_label:N", title=tr.t("drivers.importance")),
        alt.Tooltip("std_label:N", title=tr.t("drivers.std")),
    ]
    y = alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=AXIS_LABEL_LIMIT))
    base = alt.Chart(data).encode(y=y, tooltip=tooltip)
    bars = base.mark_bar(color=BLACK, cornerRadiusEnd=4).encode(
        x=alt.X("importance:Q", title=tr.t("drivers.importance_axis"))
    )
    errors = base.mark_rule(color=MUTED_TEXT, strokeWidth=1.5).encode(x="low:Q", x2="high:Q")
    labels = base.mark_text(align="left", dx=6, color=BLACK).encode(
        x="high:Q", text="value_label:N"
    )
    height = ROW_HEIGHT * len(data) + AXIS_ONLY
    chart = alt.layer(bars, errors, labels).properties(height=height)
    return _configure(chart.configure_scale(bandPaddingInner=0.3))


# ===== 7-day forecast (scope §4.3) =====
FORECAST_BLUE = "#2a78d6"  # NB §3.2 COLOR_PRED
OUTLOOK_BLUE = "#6da7ec"  # lighter step of the same ramp for days 4-7


def forecast_chart(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    tr: Translator,
    actionable_days: int,
    *,
    today: date | None = None,
) -> alt.TopLevelMixin:
    """Recent observed AQI, then the 7-day forecast with its P10-P90 band.

    Days 1-3 (actionable) and 4-7 (outlook) differ by line style, marker fill, band opacity,
    legend label, and a vertical divider, so the split never relies on colour alone.
    """
    observed = tr.t("forecast.series.observed")
    actionable = tr.t("forecast.series.actionable")
    outlook = tr.t("forecast.series.outlook")
    series_scale = alt.Scale(
        domain=[observed, actionable, outlook], range=[BLACK, FORECAST_BLUE, OUTLOOK_BLUE]
    )

    fc = forecast.assign(
        series=lambda d: d["horizon"].map(
            lambda h: actionable if h <= actionable_days else outlook
        ),
        date_label=forecast["date"].map(tr.date),
        pred_label=forecast["aqi_pred"].map(tr.number),
        band_label=[
            f"{tr.number(lo)} – {tr.number(hi)}"
            for lo, hi in zip(forecast["aqi_low"], forecast["aqi_high"], strict=True)
        ],
        category_label=forecast["category"].astype(str).map(tr.category),
    )
    # Days 1-3 and 3-7 share day 3 so that the line and band connect across the divider.
    near = fc.loc[fc["horizon"] <= actionable_days].assign(series=actionable)
    far = fc.loc[fc["horizon"] >= actionable_days].assign(series=outlook)
    hist = history.assign(
        series=observed,
        date_label=history["date"].map(tr.date),
        aqi_label=history["aqi"].map(tr.number),
    )

    y_top = max(100.0, float(max(history["aqi"].max(), forecast["aqi_high"].max())) * 1.1)
    x = alt.X("date:T", title=tr.t("chart.date"), axis=alt.Axis(format="%m-%d", labelAngle=0))
    y = alt.Y("aqi:Q", title=tr.t("chart.aqi"), scale=alt.Scale(domain=[0, y_top]))
    color = alt.Color(
        "series:N",
        title=None,
        scale=series_scale,
        legend=alt.Legend(symbolType="stroke", symbolStrokeWidth=3, symbolOpacity=1, columns=1),
    )

    hist_line = alt.Chart(hist).mark_line(strokeWidth=2).encode(x=x, y=y, color=color)
    hist_points = (
        alt.Chart(hist)
        .mark_point(size=40, opacity=0)
        .encode(
            x="date:T",
            y="aqi:Q",
            tooltip=[
                alt.Tooltip("date_label:N", title=tr.t("chart.date")),
                alt.Tooltip("aqi_label:N", title=observed),
            ],
        )
    )

    def band(frame: pd.DataFrame, opacity: float) -> alt.Chart:
        return (
            alt.Chart(frame)
            .mark_area(fillOpacity=opacity, strokeOpacity=0)
            .encode(
                x="date:T",
                y="aqi_low:Q",
                y2="aqi_high:Q",
                color=color,  # same encoding everywhere, so the layers share one legend
            )
        )

    def line(frame: pd.DataFrame, dash: list[int]) -> alt.Chart:
        return (
            alt.Chart(frame)
            .mark_line(strokeWidth=2, strokeDash=dash)
            .encode(
                x="date:T",
                y=alt.Y("aqi_pred:Q"),
                color=color,  # same encoding everywhere, so the layers share one legend
            )
        )

    tooltip = [
        alt.Tooltip("date_label:N", title=tr.t("chart.date")),
        alt.Tooltip("horizon:Q", title=tr.t("forecast.table.day")),
        alt.Tooltip("series:N", title=tr.t("forecast.table.type")),
        alt.Tooltip("pred_label:N", title=tr.t("forecast.table.forecast")),
        alt.Tooltip("band_label:N", title=tr.t("forecast.table.band")),
        alt.Tooltip("category_label:N", title=tr.t("forecast.table.category")),
    ]
    near_points = (
        alt.Chart(fc.loc[fc["horizon"] <= actionable_days])
        .mark_point(size=80, filled=True, strokeWidth=2, stroke="white")
        .encode(x="date:T", y="aqi_pred:Q", color=color, tooltip=tooltip)
    )
    far_points = (
        alt.Chart(fc.loc[fc["horizon"] > actionable_days])
        .mark_point(size=80, filled=False, strokeWidth=2.5, fill="white")
        .encode(x="date:T", y="aqi_pred:Q", color=color, tooltip=tooltip)
    )

    split = fc.loc[fc["horizon"] == actionable_days, "date"].iloc[0] + pd.to_timedelta(12, unit="h")
    divider = (
        alt.Chart(pd.DataFrame({"date": [split]}))
        .mark_rule(color=MUTED_TEXT, strokeDash=[4, 4], strokeWidth=1.5)
        .encode(x="date:T")
    )

    layers = []
    first_day, last_day = history["date"].min(), forecast["date"].max()
    if today is not None and first_day <= pd.Timestamp(today) <= last_day:
        # "Today" marker: a solid rule plus a text label, so it never relies on colour.
        now = pd.DataFrame({"date": [pd.Timestamp(today)], "label": [tr.t("forecast.chart.today")]})
        layers = [
            alt.Chart(now).mark_rule(color=RED_ACCENT, strokeWidth=2).encode(x="date:T"),
            alt.Chart(now)
            .mark_text(align="left", dx=4, dy=-6, fontWeight=600, color=BLACK)
            .encode(x="date:T", y=alt.value(0), text="label:N"),
        ]
    chart = alt.layer(
        _category_bands(tr, y_top),
        band(near, 0.30),
        band(far, 0.14),
        hist_line,
        hist_points,
        line(near, []),
        line(far, [5, 4]),
        divider,
        near_points,
        far_points,
        *layers,
    ).properties(height=CHART_HEIGHT + 60)
    return _configure(chart)


# ===== Reliability (scope §4.3, M10) =====
def horizon_accuracy_chart(
    accuracy: pd.DataFrame, tr: Translator, actionable_days: int, benchmark: float
) -> alt.TopLevelMixin:
    """Category accuracy per forecast day; days 1-3 vs 4-7 differ by colour, label, divider.

    ``accuracy`` has ``horizon`` and ``accuracy`` (percent) columns; ``benchmark`` is the best
    naive benchmark's mean accuracy, drawn as a labelled reference line.
    """
    actionable, outlook = tr.t("forecast.series.actionable"), tr.t("forecast.series.outlook")
    data = accuracy.assign(
        group=lambda d: d["horizon"].map(lambda h: actionable if h <= actionable_days else outlook),
        label=lambda d: d["accuracy"].map(lambda v: tr.percent(v)),
        day=lambda d: d["horizon"].map(lambda h: tr.t("forecast.table.day_n", day=h)),
    )
    days = data["day"].tolist()
    x = alt.X("day:N", sort=days, title=None, axis=alt.Axis(labelAngle=0))
    tooltip = [
        alt.Tooltip("day:N", title=tr.t("forecast.table.day")),
        alt.Tooltip("label:N", title=tr.t("reliability.accuracy")),
        alt.Tooltip("group:N", title=tr.t("forecast.table.type")),
    ]
    bars = (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=x,
            y=alt.Y(
                "accuracy:Q", title=tr.t("reliability.accuracy"), scale=alt.Scale(domain=[0, 100])
            ),
            color=alt.Color(
                "group:N",
                title=None,
                scale=alt.Scale(domain=[actionable, outlook], range=[FORECAST_BLUE, OUTLOOK_BLUE]),
                legend=alt.Legend(columns=1, symbolOpacity=1),
            ),
            tooltip=tooltip,
        )
    )
    labels = (
        alt.Chart(data).mark_text(dy=-8, color=BLACK).encode(x=x, y="accuracy:Q", text="label:N")
    )
    ref = pd.DataFrame({"y": [benchmark]})
    rule = alt.Chart(ref).mark_rule(color=BLACK, strokeDash=[4, 4]).encode(y="y:Q")
    split = pd.DataFrame({"day": [days[actionable_days - 1]]})
    divider = (
        alt.Chart(split)
        .mark_rule(color=MUTED_TEXT, strokeDash=[4, 4], strokeWidth=1.5)
        .encode(x=alt.X("day:N", sort=days, bandPosition=1))
    )
    # The reference line is explained in a caption under the chart: a text label here
    # would overlap the bars.
    chart = alt.layer(bars, labels, rule, divider).properties(height=CHART_HEIGHT)
    return _configure(chart)


def rmse_by_horizon_chart(
    per_h: pd.DataFrame, tr: Translator, models: list[str]
) -> alt.TopLevelMixin:
    """RMSE per forecast day for the model and both benchmarks (lower is better)."""
    data = per_h.reset_index()[["model", "horizon", "RMSE"]].assign(
        model_label=lambda d: d["model"].map(lambda m: tr.t(f"reliability.model.{m}")),
        value_label=lambda d: d["RMSE"].map(tr.number),
    )
    names = [tr.t(f"reliability.model.{m}") for m in models]
    color = alt.Color(
        "model_label:N",
        title=None,
        scale=alt.Scale(domain=names, range=YEAR_COLORS[: len(names)]),
        legend=alt.Legend(columns=1),
    )
    tooltip = [
        alt.Tooltip("model_label:N", title=tr.t("reliability.model_col")),
        alt.Tooltip("horizon:O", title=tr.t("forecast.table.day")),
        alt.Tooltip("value_label:N", title="RMSE"),
    ]
    base = alt.Chart(data).encode(
        x=alt.X("horizon:O", title=tr.t("forecast.table.day"), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("RMSE:Q", title=tr.t("reliability.rmse_axis"), scale=alt.Scale(zero=True)),
        color=color,
        tooltip=tooltip,
    )
    lines = base.mark_line(strokeWidth=2)
    points = base.mark_point(size=64, filled=True, stroke="white", strokeWidth=2)
    return _configure((lines + points).properties(height=CHART_HEIGHT))


def actual_vs_predicted_chart(
    frame: pd.DataFrame, tr: Translator, cams_50r1: str
) -> alt.TopLevelMixin:
    """Observed vs forecast AQI over the test period for one horizon, with the 50r1 upgrade."""
    observed, predicted = tr.t("reliability.observed"), tr.t("reliability.predicted")
    data = frame.assign(
        date_label=frame["target_date"].map(tr.date),
        true_label=frame["y_true"].map(tr.number),
        pred_label=frame["y_pred"].map(tr.number),
    )
    long = data.melt(
        id_vars=["target_date", "date_label", "true_label", "pred_label"],
        value_vars=["y_true", "y_pred"],
        var_name="key",
        value_name="aqi",
    ).assign(series=lambda d: d["key"].map({"y_true": observed, "y_pred": predicted}))
    lines = (
        alt.Chart(long)
        .mark_line(strokeWidth=1.8)
        .encode(
            x=alt.X("target_date:T", title=tr.t("chart.date"), axis=alt.Axis(format="%Y-%m")),
            y=alt.Y("aqi:Q", title=tr.t("chart.aqi")),
            color=alt.Color(
                "series:N",
                title=None,
                scale=alt.Scale(domain=[observed, predicted], range=[BLACK, FORECAST_BLUE]),
                legend=alt.Legend(symbolType="stroke", symbolStrokeWidth=3, symbolOpacity=1),
            ),
        )
    )
    tooltip = [
        alt.Tooltip("date_label:N", title=tr.t("chart.date")),
        alt.Tooltip("true_label:N", title=observed),
        alt.Tooltip("pred_label:N", title=predicted),
    ]
    catcher = (
        alt.Chart(data)
        .mark_rule(opacity=0, strokeWidth=10)
        .encode(x="target_date:T", tooltip=tooltip)
    )
    marker = pd.DataFrame({"date": [pd.Timestamp(cams_50r1)], "label": ["CAMS 50r1"]})
    rule = alt.Chart(marker).mark_rule(color=BLACK, strokeDash=[4, 4]).encode(x="date:T")
    rule_label = (
        alt.Chart(marker)
        .mark_text(align="left", dx=4, dy=-6, color=BLACK)
        .encode(x="date:T", y=alt.value(0), text="label:N")
    )
    chart = alt.layer(lines, rule, rule_label, catcher).properties(height=CHART_HEIGHT)
    return _configure(chart)
