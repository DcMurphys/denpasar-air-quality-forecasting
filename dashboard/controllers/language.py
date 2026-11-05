"""Language toggle in the sidebar (first visit follows the browser) and catalogs."""

from pathlib import Path

import streamlit as st

from dashboard.views.i18n import (
    DEFAULT_LANG,
    LANGUAGES,
    Translator,
    initial_language,
    load_catalogs,
)

LOCALE_DIR = Path(__file__).resolve().parents[1] / "locales"
LANG_KEY = "lang"
# Compact toggle labels: flag emoji plus language code (emoji flags render as letters on Windows).
LANGUAGE_BADGES = {"id": "🇮🇩 ID", "en": "🇬🇧 EN"}


@st.cache_data(show_spinner=False)
def _cached_catalogs(
    locale_dir: str, mtimes: tuple[float, ...]
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Load the catalogs once per set of file modification times."""
    return load_catalogs(Path(locale_dir))


def _mtimes(locale_dir: Path) -> tuple[float, ...]:
    paths = (locale_dir / f"{lang}.json" for lang in LANGUAGES)
    return tuple(path.stat().st_mtime if path.is_file() else 0.0 for path in paths)


def translator(locale_dir: Path = LOCALE_DIR) -> Translator:
    """The Translator for the language chosen in this session, without rendering a widget."""
    catalogs, _ = _cached_catalogs(str(locale_dir), _mtimes(locale_dir))
    return Translator(catalogs, st.session_state.get(LANG_KEY, DEFAULT_LANG))


def select_language(locale_dir: Path = LOCALE_DIR) -> tuple[Translator, list[str]]:
    """Render the toggle at the top of the sidebar; return a Translator and the codes of
    missing locale files. The sidebar stays in view while the page scrolls, so the language
    can be switched from anywhere on a long page. Call it from app.py before the page runs."""
    catalogs, missing = _cached_catalogs(str(locale_dir), _mtimes(locale_dir))
    st.session_state.setdefault(LANG_KEY, initial_language(st.context.locale))
    with st.sidebar:
        lang = st.segmented_control(
            catalogs[DEFAULT_LANG]["language.label"],  # bilingual, so it reads in either language
            options=LANGUAGES,
            format_func=LANGUAGE_BADGES.get,
            required=True,  # a language is always selected
            key=LANG_KEY,
        )
    return Translator(catalogs, lang), missing
