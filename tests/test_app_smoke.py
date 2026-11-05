"""Smoke tests of the real app through dashboard/app.py (scope §8)."""

import html
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pytest
from streamlit.testing.v1 import AppTest

from aqi_forecasting.config import AQI_CATEGORIES, AQI_LABELS, DATA_DIR
from dashboard.views.i18n import category_key

APP = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")
PAGES = ("overview", "drivers", "forecast", "about")
TIMEOUT = 60


def _run(lang: str = "id") -> AppTest:
    app = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    if lang != "id":
        app.segmented_control(key="lang").set_value(lang).run()
    return app


def _day_cards(app: AppTest) -> list[str]:
    """Plain text of the "today" / "tomorrow" cards."""
    block = next(b.value for b in app.markdown if 'class="day-grid"' in b.value)
    cards = [part.split(">", 1)[1] for part in block.split('class="day-card"')[1:]]
    return [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", card)).split()) for card in cards]


def _metric_values(app: AppTest) -> list[str]:
    """Values of the KPI cards (rendered as HTML so that they wrap instead of truncating)."""
    values = []
    for block in app.markdown:
        for value in re.findall(r'class="kpi-value"[^>]*>(.*?)</div>', block.value):
            values.append(html.unescape(value))
    return values


@pytest.mark.parametrize("lang", ["id", "en"])
@pytest.mark.parametrize("page", PAGES)
def test_every_page_runs_in_both_languages(page: str, lang: str) -> None:
    app = _run(lang)
    app.switch_page(f"page_scripts/{page}.py").run()
    assert not app.exception
    assert not app.error


def test_navigation_lists_four_translated_pages() -> None:
    app = _run("id")
    titles = [page.title for page in app.session_state["pages"].values()]
    assert titles == ["Ikhtisar", "Faktor Penyebab", "Prakiraan 7 Hari", "Tentang"]
    app.segmented_control(key="lang").set_value("en").run()
    titles = [page.title for page in app.session_state["pages"].values()]
    assert titles == ["Overview", "Key Factors", "7-Day Forecast", "About"]


def test_overview_current_status_indonesian() -> None:
    app = _run("id")
    assert app.title[0].value == "Ikhtisar"
    values = _metric_values(app)
    assert "5 dari 1.548 (0,3 %)" in values
    assert "52,4 / 51,3" in values
    assert "11,0 µg/m³" in values
    assert "12,1 %" in values
    # Today and tomorrow come first (UX review, priority 1).
    assert app.subheader[0].value == "Udara hari ini dan besok"
    assert "2026-10-30 (5 hari lalu)" in app.warning[0].value
    cards = _day_cards(app)
    assert cards[0].startswith("Hari ini · 2026-11-04 55,9 US AQI: Sedang Gambaran hari ke-5")
    assert cards[1].startswith("Besok · 2026-11-05 55,9 US AQI: Sedang Gambaran hari ke-6")
    assert "Kelompok sensitif: Bila Anda sangat sensitif" in cards[0]  # EPA advice (priority 2)
    assert any("US EPA" in caption.value for caption in app.caption)


def test_overview_current_status_english() -> None:
    app = _run("en")
    values = _metric_values(app)
    assert "5 of 1,548 (0.3%)" in values
    assert "52.4 / 51.3" in values
    cards = _day_cards(app)
    assert cards[0].startswith("Today · 2026-11-04 55.9 US AQI: Moderate Outlook day 5")
    assert "Everyone: Air quality is acceptable" in cards[0]


def test_missing_forecast_only_affects_today_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copy(DATA_DIR / "dashboard_daily.parquet", tmp_path)
    monkeypatch.setenv("AQI_DATA_DIR", str(tmp_path))
    app = _run("id")
    assert not app.exception
    assert len(app.error) == 1
    assert "prakiraan terbaru" in app.error[0].value
    assert "5 dari 1.548 (0,3 %)" in _metric_values(app)  # KPIs still render


def test_missing_daily_data_shows_a_fatal_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AQI_DATA_DIR", str(tmp_path))
    app = _run("id")
    assert not app.exception
    assert app.title[0].value == "Data tidak dapat ditampilkan"
    assert "data harian" in app.error[0].value
    assert not _metric_values(app)


# ===== Overview history tabs (M7) =====
def test_overview_tabs_and_annual_table() -> None:
    app = _run("id")
    assert [tab.label for tab in app.tabs] == [
        "Tren",
        "KPI tahunan",
        "Pola musiman",
        "Hari tidak sehat",
    ]
    annual = app.table[0].value
    assert annual["Rata-rata AQI"].tolist() == ["50,63", "52,85", "51,18", "52,21", "52,27"]
    assert annual["Tahun"].tolist() == ["2022*", "2023", "2024", "2025", "2026*"]
    assert any("Tahun bertanda * adalah" in c.value for c in app.caption)  # not a bullet
    assert len(app.get("vega_lite_chart")) == 3  # trend, monthly profile, seasons


def test_filters_change_tabs_but_not_current_status() -> None:
    app = _run("en")
    before = _metric_values(app)
    app.slider(key="ov_years").set_value((2024, 2025)).run()
    app.segmented_control(key="ov_season").set_value("Wet").run()
    assert not app.exception
    annual = app.table[0].value
    assert annual["Year"].tolist() == ["2024", "2025"]
    assert _metric_values(app) == before  # Current status ignores the filters
    unhealthy = app.table[-1].value
    assert unhealthy["Date"].tolist() == ["2024-11-25", "2024-11-26", "2025-02-05"]


# ===== Key Factors page (M8) =====
def _drivers_page(lang: str) -> AppTest:
    app = _run(lang)
    app.switch_page("page_scripts/drivers.py").run()
    assert not app.exception
    return app


# A decimal number not glued to a letter, so "PM2.5" is not read as a value.
NUMBER = r"(?<![A-Za-z\d])-?\d+[.,]\d+"


def _findings_text(app: AppTest) -> str:
    return next(block.value for block in app.markdown if block.value.startswith("- "))


def test_drivers_page_in_both_languages() -> None:
    id_app, en_app = _drivers_page("id"), _drivers_page("en")
    assert id_app.title[0].value == "Faktor Penyebab"
    assert en_app.title[0].value == "Key Factors"
    id_text, en_text = _findings_text(id_app), _findings_text(en_app)
    assert "0,91" in id_text and "0.91" in en_text
    # The same numbers appear in both languages; only the decimal separator differs.
    assert re.findall(NUMBER, id_text) == [n.replace(".", ",") for n in re.findall(NUMBER, en_text)]
    assert len(en_app.get("vega_lite_chart")) == 3  # pollutants, weather, importance
    en_app.segmented_control(key="drv_horizon").set_value("next_day").run()
    assert not en_app.exception


def test_missing_importance_only_hides_its_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aqi_forecasting.config import ARTIFACT_DIR

    shutil.copy(ARTIFACT_DIR / "preprocessing_config.json", tmp_path)
    monkeypatch.setenv("AQI_ARTIFACT_DIR", str(tmp_path))
    app = _drivers_page("id")
    assert len(app.error) == 1
    assert "tingkat kepentingan variabel" in app.error[0].value
    assert len(app.get("vega_lite_chart")) == 2  # the correlation charts still render


# ===== 7-Day Forecast page (M9) =====
def _forecast_page(lang: str) -> AppTest:
    app = _run(lang)
    app.switch_page("page_scripts/forecast.py").run()
    assert not app.exception
    return app


def _table_rows(app: AppTest, css_class: str) -> list[list[str]]:
    block = next(b.value for b in app.markdown if css_class in b.value)
    rows = re.findall(r"<tr>(.*?)</tr>", block.split("<tbody>")[1])
    return [
        [
            html.unescape(re.sub(r"<[^>]+>", "", cell))
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", r)
        ]
        for r in rows
    ]


def test_forecast_page_indonesian() -> None:
    app = _forecast_page("id")
    assert app.title[0].value == "Prakiraan 7 Hari"
    text = " ".join(block.value for block in app.markdown)
    assert "Prakiraan per 2026-10-30" in text
    assert "hari ke-1 sampai ke-3 dapat dipakai" in text.lower()
    assert "Tidak ada peringatan" in app.success[0].value and "67,1" in app.success[0].value
    near, far = _table_rows(app, "forecast-actionable"), _table_rows(app, "forecast-outlook")
    assert [row[0] for row in near] == [
        "2026-10-31hari ke-1 · sudah lewat",
        "2026-11-01hari ke-2 · sudah lewat",
        "2026-11-02hari ke-3 · sudah lewat",
    ]
    assert [row[0] for row in far] == [
        "2026-11-03hari ke-4 · sudah lewat",
        "2026-11-04hari ke-5 · hari ini",
        "2026-11-05hari ke-6 · besok",
        "2026-11-06hari ke-7",
    ]
    preds = [row[1] for row in near + far]
    assert preds == ["54,0", "54,2", "54,6", "55,5", "55,9", "55,9", "55,6"]  # NB §8.2
    assert near[0][2] == "46,1 – 61,2" and far[-1][2] == "37,9 – 69,4"
    assert all(row[3] == "Sedang" for row in near + far)
    assert "Kategori US AQI" in text  # the header names the scale (Q12)
    assert len(app.get("vega_lite_chart")) == 4  # forecast + three reliability charts


def test_forecast_page_english_labels() -> None:
    app = _forecast_page("en")
    text = " ".join(block.value for block in app.markdown)
    assert "Forecast (actionable) · days 1 to 3" in text
    assert "Outlook (indicative only) · days 4 to 7" in text
    assert "No advisory" in app.success[0].value and "67.1" in app.success[0].value


def test_missing_forecast_shows_error_on_forecast_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copy(DATA_DIR / "dashboard_daily.parquet", tmp_path)
    monkeypatch.setenv("AQI_DATA_DIR", str(tmp_path))
    app = _forecast_page("id")
    assert len(app.error) == 1 and "prakiraan terbaru" in app.error[0].value
    assert any("Prakiraan per 2026-10-30" in b.value for b in app.markdown)


def test_forecast_history_window_switch() -> None:
    app = _forecast_page("id")
    assert app.segmented_control(key="fc_history").value == 14
    app.segmented_control(key="fc_history").set_value(60).run()
    assert not app.exception


# ===== Readability (UX review, priority 3) =====
def test_global_readability_styles_are_injected() -> None:
    app = _run("id")
    css = " ".join(element.proto.body for element in app.get("html"))
    assert "min-height: 44px" in css
    assert "opacity: 1 !important" in css


# ===== Glossary and sources (UX priorities 4 and 6) =====
@pytest.mark.parametrize(
    ("page", "expected"),
    [
        ("overview", ["US AQI", "P10–P90", "PM2.5", "CAMS"]),
        ("drivers", ["Korelasi Spearman", "Kenaikan RMSE"]),
        ("forecast", ["P10–P90", "Tingkat 1 dan 2"]),
    ],
)
def test_glossary_explains_terms_on_each_page(page: str, expected: list[str]) -> None:
    app = _run("id")
    app.switch_page(f"page_scripts/{page}.py").run()
    assert not app.exception
    labels = [e.label for e in app.expander]
    assert "Arti istilah" in labels
    text = " ".join(block.value for block in app.markdown)
    for term in expected:
        assert term in text, term
    assert "{" not in text  # every placeholder filled


def test_sidebar_cites_sources_with_links() -> None:
    app = _run("en")
    text = " ".join(caption.value for caption in app.sidebar.caption)
    for url in (
        "atmosphere.copernicus.eu",
        "kaggle.com/datasets/danielaijdkx",
        "airnow.gov",
        "who.int",
    ):
        assert url in text, url


# ===== Expert features (UX priority 8) =====
def test_trend_variable_and_date_range_and_downloads() -> None:
    from datetime import date

    app = _run("en")
    app.selectbox(key="ov_trend_var").set_value("pm2_5_mean").run()
    assert not app.exception
    dates = next(d for d in app.date_input if d.key.startswith("ov_trend_dates_"))
    dates.set_value((date(2025, 1, 1), date(2025, 3, 31))).run()
    assert not app.exception
    downloads = app.get("download_button")
    assert len(downloads) == 2  # trend + annual KPIs on the Overview


def test_downloads_on_drivers_and_forecast_pages() -> None:
    for page in ("drivers", "forecast"):
        app = _run("id")
        app.switch_page(f"page_scripts/{page}.py").run()
        assert not app.exception
        assert len(app.get("download_button")) == 1, page


# ===== Reliability section (M10) =====
def test_reliability_section_both_languages() -> None:
    app = _forecast_page("id")
    assert "Seberapa andal prakiraan ini?" in [s.value for s in app.subheader]
    text = " ".join(block.value for block in app.markdown)
    assert "76,96\u00a0%" in text and "72,47\u00a0%" in text  # B3 (NB §7.4)
    assert "Tidak terpenuhi" in text and "16,79\u00a0%" in text  # D5 missed
    assert "Detail model" in [e.label for e in app.expander]
    assert len(app.get("vega_lite_chart")) == 4  # forecast, accuracy, RMSE, actual vs predicted
    app.segmented_control(key="fc_avp_horizon").set_value(5).run()
    assert not app.exception

    en = _forecast_page("en")
    en_text = " ".join(block.value for block in en.markdown)
    assert "Not met" in en_text and "76.96%" in en_text


def test_missing_predictions_only_hides_reliability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("dashboard_daily.parquet", "forecast_latest.parquet", "metrics_rf_tuned.parquet"):
        shutil.copy(DATA_DIR / name, tmp_path)
    monkeypatch.setenv("AQI_DATA_DIR", str(tmp_path))
    app = _forecast_page("id")
    assert len(app.error) == 1 and "prediksi model" in app.error[0].value
    assert _table_rows(app, "forecast-actionable")  # the forecast section still renders


# ===== About page (M11) =====


def _about_page(lang: str) -> AppTest:
    app = _run(lang)
    app.switch_page("page_scripts/about.py").run()
    assert not app.exception
    return app


def _page_text(app: AppTest) -> str:
    return " ".join(b.value for b in [*app.markdown, *app.caption, *app.subheader, *app.title])


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("id", ["1.548 hari", "b818fb605cff", "1.512 hari", "AQI bukan ISPU", "Keterbatasan"]),
        ("en", ["1,548 days", "b818fb605cff", "1,512 days", "is not ISPU", "Limitations"]),
    ],
)
def test_about_page_both_languages(lang: str, expected: list[str]) -> None:
    app = _about_page(lang)
    text = _page_text(app)
    for snippet in expected:
        assert snippet in text, snippet
    assert "about." not in text and "glossary." not in text  # no raw keys
    assert "{" not in re.sub(r"<style.*?</style>|style=\"[^\"]*\"", "", text, flags=re.S)
    assert not app.error


def test_about_renders_without_forecast_or_predictions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copy(DATA_DIR / "dashboard_daily.parquet", tmp_path)
    monkeypatch.setenv("AQI_DATA_DIR", str(tmp_path))
    app = _about_page("id")
    assert not app.error
    assert "1.512 hari" in _page_text(app)


def test_about_shows_error_card_without_model_params(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aqi_forecasting.config import ARTIFACT_DIR

    shutil.copy(ARTIFACT_DIR / "preprocessing_config.json", tmp_path)
    monkeypatch.setenv("AQI_ARTIFACT_DIR", str(tmp_path))
    app = _about_page("id")
    assert len(app.error) == 1 and "parameter model" in app.error[0].value
    assert "Keterbatasan" in _page_text(app)  # later sections still render


# ===== Translation review (M12) =====


def _visible_text(app: AppTest) -> str:
    parts = []
    for kind in ("markdown", "caption", "title", "subheader", "header", "info", "warning"):
        parts += [element.value for element in app.get(kind)]
    parts += [table.value.to_string() for table in app.get("table")]
    text = re.sub(r"<style.*?</style>", "", " ".join(parts), flags=re.S)
    text = re.sub(r'(style|class|href|src)="[^"]*"|\]\([^)]*\)|<[^>]+>', " ", text)
    return html.unescape(text).replace("PM2.5", "PM")  # a pollutant name, not a value


def _numbers(text: str, lang: str) -> Counter:
    """Every number on the page, normalised from the language's separators."""
    text = re.sub(r"\d{4}-\d{2}-\d{2}", lambda m: m.group().replace("-", ""), text)
    thousands, decimal = (".", ",") if lang == "id" else (",", ".")
    tokens = (t.rstrip(".,") for t in re.findall(r"\d[\d.,]*\d|\d", text))
    return Counter(t.replace(thousands, "").replace(decimal, ".") for t in tokens)


@pytest.mark.parametrize("page", PAGES)
def test_numbers_are_identical_across_languages(page: str) -> None:
    found = {}
    for lang in ("id", "en"):
        app = _run(lang)
        app.switch_page(f"page_scripts/{page}.py").run()
        found[lang] = _numbers(_visible_text(app), lang)
    assert sum(found["id"].values()) > 20
    assert found["id"] == found["en"], (found["id"] - found["en"], found["en"] - found["id"])


# ===== Chart tooltips =====


def _layers(spec: dict):
    yield spec
    for child in spec.get("layer", []):
        yield from _layers(child)


@pytest.mark.parametrize("page", ("overview", "drivers", "forecast"))
def test_charts_show_no_raw_default_tooltips(page: str) -> None:
    """Layers without a translated tooltip (category bands, P10–P90 area, rules) show none,
    instead of Streamlit's default list of raw fields such as ``lower`` and a hex colour."""
    app = _run("id")
    app.switch_page(f"page_scripts/{page}.py").run()
    charts = app.get("vega_lite_chart")
    assert charts
    checked = 0
    for chart in charts:
        spec = json.loads(chart.proto.spec)
        for layer in _layers(spec):
            if "mark" not in layer:
                continue
            checked += 1
            mark = layer["mark"] if isinstance(layer["mark"], dict) else {}
            has_tooltip = "tooltip" in layer.get("encoding", {})
            assert has_tooltip or ("tooltip" in mark and mark["tooltip"] is None), layer["mark"]
    assert checked


# ===== NFR pass (M13) =====

_AQI_HEX = "|".join(color for _, _, color in AQI_CATEGORIES)


@pytest.mark.parametrize("lang", ["id", "en"])
@pytest.mark.parametrize("page", PAGES)
def test_every_aqi_colour_carries_a_text_label(page: str, lang: str) -> None:
    """Scope §7: an AQI category colour always comes with its translated name, and the yellow
    "Moderate" colour is never used as a text colour."""
    app = _run(lang)
    app.switch_page(f"page_scripts/{page}.py").run()
    html_blocks = " ".join(block.value for block in app.markdown)
    names = set(_category_names(lang))
    coloured = re.findall(
        rf'<span style="background:(?:{_AQI_HEX});[^"]*">(.*?)</span>', html_blocks, flags=re.I
    )
    for text in coloured:
        assert any(name in html.unescape(text) for name in names), text
    assert not re.search(r"(?<!-)color:\s*#ffff00", html_blocks, flags=re.I)
    for chart in app.get("vega_lite_chart"):
        if "label_y" in chart.proto.spec:  # category bands: every band has a text name
            bands = _band_names(chart.proto)
            assert bands and set(bands) <= names


def _category_names(lang: str) -> list[str]:
    catalog = json.loads((Path(APP).parent / "locales" / f"{lang}.json").read_text())
    return [catalog[category_key(label)] for label in AQI_LABELS]


def _band_names(proto) -> list[str]:
    """Names of the category bands, read from the chart's Arrow datasets."""
    names = []
    for dataset in proto.datasets:
        frame = pa.ipc.open_stream(dataset.data.data).read_all().to_pandas()
        if "label_y" in frame:
            names += frame["name"].tolist()
    return names


def test_sidebar_flower_is_served_as_png() -> None:
    """The sidebar shows dashboard/assets/jepun.png as a PNG (not re-encoded as JPEG)."""
    app = _run("id")
    images = app.sidebar.get("image")
    assert len(images) == 1
    url = images[0].proto.imgs[0].url
    assert url.endswith(".png"), url
