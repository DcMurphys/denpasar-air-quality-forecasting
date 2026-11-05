"""Translation catalogs, formatting helpers, and the language toggle (scope §5.9, §8)."""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from aqi_forecasting.config import AQI_LABELS, POLLUTANT_FEATURES, WEATHER_FEATURES
from dashboard.controllers.language import LOCALE_DIR
from dashboard.views.i18n import Translator, category_key, load_catalogs, validate_catalogs

ARTIFACT_NAMES = [
    "dashboard_daily",
    "forecast_latest",
    "predictions",
    "metrics",
    "preprocessing_config",
    "model_params",
    "feature_importance",
]


@pytest.fixture(scope="module")
def catalogs() -> dict[str, dict[str, str]]:
    loaded, missing = load_catalogs(LOCALE_DIR)
    assert missing == []
    return loaded


@pytest.fixture(scope="module")
def id_tr(catalogs: dict) -> Translator:
    return Translator(catalogs, "id")


@pytest.fixture(scope="module")
def en_tr(catalogs: dict) -> Translator:
    return Translator(catalogs, "en")


# ===== Catalog integrity =====
def test_catalogs_have_identical_keys_and_placeholders(catalogs: dict) -> None:
    assert validate_catalogs(catalogs) == []


def test_required_keys_exist(catalogs: dict, preprocessing_config: dict) -> None:
    features = {
        *preprocessing_config["feature_columns"],
        *POLLUTANT_FEATURES,
        *WEATHER_FEATURES,
        "post_cams_50r1",
    }
    required = {
        *(f"page.{page}" for page in ("overview", "drivers", "forecast", "about")),
        *(category_key(label) for label in AQI_LABELS),
        "season.Dry",
        "season.Wet",
        *(f"feature.{name}" for name in features),
        *(f"error.{kind}" for kind in ("missing", "unreadable", "invalid")),
        *(f"artifact.{name}" for name in ARTIFACT_NAMES),
        *(f"month.short.{m}" for m in range(1, 13)),
        # Plain-language advice for every category and audience (UX review, priority 2).
        *(
            category_key(label).replace("aqi.category.", "advice.") + f".{who}"
            for label in AQI_LABELS
            for who in ("everyone", "sensitive")
        ),
    }
    for lang, catalog in catalogs.items():
        assert required <= catalog.keys(), (lang, sorted(required - catalog.keys()))


def test_validate_catalogs_reports_problems() -> None:
    broken = {
        "id": {"a": "Halo {name}", "b": ""},
        "en": {"a": "Hello {nama}", "c": "only in English"},
    }
    problems = validate_catalogs(broken)
    assert "id: missing key c" in problems
    assert "en: missing key b" in problems
    assert "placeholders differ for a" in problems
    assert "id: empty value for b" in problems


# ===== Formatting =====
def test_number_formatting(id_tr: Translator, en_tr: Translator) -> None:
    assert id_tr.number(52.4) == "52,4"
    assert en_tr.number(52.4) == "52.4"
    assert id_tr.number(1548, decimals=0) == "1.548"
    assert en_tr.number(1548, decimals=0) == "1,548"
    assert id_tr.percent(12.1) == "12,1 %"  # non-breaking space before % in Indonesian
    assert en_tr.percent(12.1) == "12.1%"


def test_dates_are_iso_in_both_languages(id_tr: Translator, en_tr: Translator) -> None:
    day = date(2026, 11, 4)
    assert id_tr.date(day) == en_tr.date(day) == "2026-11-04"
    assert id_tr.date(pd.Timestamp("2026-10-30")) == "2026-10-30"


def test_month_names(id_tr: Translator, en_tr: Translator) -> None:
    assert id_tr.month(8) == "Agu"
    assert en_tr.month(8) == "Aug"


def test_categories_seasons_and_features(id_tr: Translator, en_tr: Translator) -> None:
    assert id_tr.category("Unhealthy for Sensitive Groups") == "Tidak Sehat bagi Kelompok Sensitif"
    assert en_tr.category("Moderate") == "Moderate"
    assert id_tr.season("Dry") == "Musim kemarau"
    assert id_tr.feature("pm2_5_mean") == "Partikel halus PM2.5 (µg/m³)"
    assert en_tr.feature("aqi_roll30_std") == "AQI fluctuation, last 30 days"


def test_page_titles(id_tr: Translator, en_tr: Translator) -> None:
    assert [id_tr.t(f"page.{p}") for p in ("overview", "drivers", "forecast", "about")] == [
        "Ikhtisar",
        "Faktor Penyebab",
        "Prakiraan 7 Hari",
        "Tentang",
    ]
    assert en_tr.t("page.drivers") == "Key Factors"
    assert en_tr.t("page.forecast") == "7-Day Forecast"


def test_data_values_are_placeholders_not_text(
    catalogs: dict, id_tr: Translator, en_tr: Translator
) -> None:
    """The horizon and the CAMS upgrade months come from shared constants (M12)."""
    for catalog in catalogs.values():
        assert "{horizon}" in catalog["page.forecast"]
        assert "{year}" in catalog["feature.post_cams_50r1"]
        for key, text in catalog.items():
            if key != "advice.source":  # the cited US EPA document's own date
                assert "2024" not in text and "2026" not in text, key
    assert id_tr.feature("post_cams_49r1") == "Setelah pembaruan model CAMS (Nov 2024)"
    assert en_tr.feature("post_cams_50r1") == "After CAMS model update (May 2026)"
    assert id_tr.t("page.forecast", horizon=5) == "Prakiraan 5 Hari"  # callers can override


def test_user_facing_messages_avoid_technical_terms(catalogs: dict) -> None:
    """Errors and warnings are plain language; technical details go to the log only."""
    banned = ("notebook", "path", "parquet", "export", "ekspor", "{path}")
    for catalog in catalogs.values():
        for key, text in catalog.items():
            if key.startswith(("error.", "warning.")):
                assert not any(word in text.lower() for word in banned), (key, text)


def test_placeholders_are_filled(id_tr: Translator) -> None:
    text = id_tr.t("error.missing", artifact="data harian")
    assert "data harian" in text and "{" not in text


# ===== Fallbacks =====
def test_missing_key_falls_back_to_english(catalogs: dict) -> None:
    partial = {
        "id": {k: v for k, v in catalogs["id"].items() if k != "page.about"},
        "en": catalogs["en"],
    }
    assert Translator(partial, "id").t("page.about") == "About"


def test_missing_locale_file_falls_back(tmp_path: Path, catalogs: dict) -> None:
    (tmp_path / "en.json").write_text(json.dumps(catalogs["en"]), encoding="utf-8")
    loaded, missing = load_catalogs(tmp_path)
    assert missing == ["id"]
    assert Translator(loaded, "id").t("page.about") == "About"


# ===== Language toggle =====
def _language_app() -> None:
    import streamlit as st

    from dashboard.controllers.language import select_language

    translator, _ = select_language()
    st.title(translator.t("app.title"))


def test_language_toggle_defaults_to_indonesian_and_switches() -> None:
    app = AppTest.from_function(_language_app).run()
    assert not app.exception
    assert app.title[0].value == "Kualitas Udara Denpasar"
    # In the sidebar, so it stays reachable while a long page scrolls.
    assert [c.key for c in app.sidebar.segmented_control] == ["lang"]
    toggle = app.segmented_control(key="lang")
    # Streamlit renders the leading flag emoji as the option icon, so the text is the code.
    assert toggle.options == ["ID", "EN"]
    toggle.set_value("en").run()
    assert app.title[0].value == "Denpasar Air Quality"


# ===== First-visit language (UX priority 5) =====
@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("id-ID", "id"),
        ("id", "id"),
        (None, "id"),
        ("en-AU", "en"),
        ("ms-MY", "en"),
        ("ko-KR", "en"),
    ],
)
def test_initial_language_follows_the_browser(locale: str | None, expected: str) -> None:
    from dashboard.views.i18n import initial_language

    assert initial_language(locale) == expected


def test_browser_tab_titles_are_descriptive(id_tr: Translator, en_tr: Translator) -> None:
    from dashboard.views.shell import tab_title

    assert tab_title(id_tr, "forecast") == "Prakiraan AQI 7 hari · Kualitas Udara Denpasar"
    assert tab_title(en_tr, "overview") == "Today's AQI and trends · Denpasar Air Quality"
    for tr in (id_tr, en_tr):
        titles = [tab_title(tr, p) for p in ("overview", "drivers", "forecast", "about")]
        assert len(set(titles)) == 4 and all(tr.t("app.title") in t for t in titles)
