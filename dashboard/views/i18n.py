"""Translations and per-language number and date formatting (scope §4, §5.9).

All user-facing strings live in ``dashboard/locales/{id,en}.json``. Numbers are never typed into
translations; they are passed as placeholder values and formatted here.
"""

import json
import logging
import string
from datetime import date
from functools import lru_cache
from pathlib import Path

from aqi_forecasting.config import CAMS_UPGRADES, HORIZON

LANGUAGES = ("id", "en")
DEFAULT_LANG = "id"
FALLBACK_LANG = "en"

logger = logging.getLogger(__name__)

# Values any string may use without the caller passing them, so labels such as the page title
# "Prakiraan {horizon} Hari" never hard-code a number (M12). The artifact loader checks that
# preprocessing_config.json agrees with these constants.
SHARED_VALUES: dict[str, object] = {"horizon": HORIZON}


@lru_cache(maxsize=1024)
def _fields(text: str) -> frozenset[str]:
    return frozenset(field for _, field, _, _ in string.Formatter().parse(text) if field)


def placeholders(text: str) -> set[str]:
    """Return the named placeholders in a template string."""
    return {field for _, field, _, _ in string.Formatter().parse(text) if field}


def validate_catalogs(catalogs: dict[str, dict[str, str]]) -> list[str]:
    """Return problems: differing key sets, empty strings, or differing placeholders."""
    problems: list[str] = []
    reference_lang, *others = list(catalogs)
    reference = catalogs[reference_lang]
    for lang in others:
        catalog = catalogs[lang]
        for key in sorted(reference.keys() - catalog.keys()):
            problems.append(f"{lang}: missing key {key}")
        for key in sorted(catalog.keys() - reference.keys()):
            problems.append(f"{reference_lang}: missing key {key}")
        for key in sorted(reference.keys() & catalog.keys()):
            if placeholders(reference[key]) != placeholders(catalog[key]):
                problems.append(f"placeholders differ for {key}")
    for lang, catalog in catalogs.items():
        empty = [key for key, text in catalog.items() if not text]
        problems.extend(f"{lang}: empty value for {key}" for key in empty)
    return problems


def load_catalogs(locale_dir: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Read every locale file; a missing file falls back to another language.

    Returns the catalogs and the codes of missing languages (shown as a warning banner).
    """
    catalogs: dict[str, dict[str, str]] = {}
    for lang in LANGUAGES:
        path = Path(locale_dir) / f"{lang}.json"
        if path.is_file():
            catalogs[lang] = json.loads(path.read_text(encoding="utf-8"))
    if not catalogs:
        raise FileNotFoundError(f"No locale files found in {locale_dir}")
    missing = [lang for lang in LANGUAGES if lang not in catalogs]
    for lang in missing:
        catalogs[lang] = next(iter(catalogs.values()))
        logger.warning("Locale file %s.json is missing; using another language", lang)
    for problem in validate_catalogs(catalogs):
        logger.warning("Locale problem: %s", problem)
    return catalogs, missing


def initial_language(browser_locale: str | None) -> str:
    """First-visit language: Indonesian for ``id-*`` browsers or an unknown locale, English
    for any other browser language (UX priority 5). The toggle always overrides it."""
    if browser_locale is None or browser_locale.lower().startswith("id"):
        return DEFAULT_LANG
    return FALLBACK_LANG


def category_key(label: str) -> str:
    """Translation key of a US AQI category given its English EPA label."""
    return "aqi.category." + label.lower().replace(" ", "_")


class Translator:
    """Look up strings and format numbers and dates for one language."""

    def __init__(self, catalogs: dict[str, dict[str, str]], lang: str = DEFAULT_LANG) -> None:
        self.catalogs = catalogs
        self.lang = lang if lang in catalogs else DEFAULT_LANG

    def t(self, key: str, **values: object) -> str:
        """Translate ``key`` and fill its placeholders; missing keys fall back to English."""
        text = self.catalogs[self.lang].get(key)
        if text is None:
            logger.warning("Missing translation for %r in %r", key, self.lang)
            text = self.catalogs.get(FALLBACK_LANG, {}).get(key, key)
        if not _fields(text):
            return text
        return text.format(**{**SHARED_VALUES, **values})

    def number(self, value: float, decimals: int = 1) -> str:
        """Format a number with this language's decimal and thousands separators."""
        formatted = f"{value:,.{decimals}f}"
        decimal_sep, thousands_sep = self.t("format.decimal_sep"), self.t("format.thousands_sep")
        return formatted.translate(str.maketrans({",": thousands_sep, ".": decimal_sep}))

    def percent(self, value: float, decimals: int = 1) -> str:
        """Format a percentage, e.g. 12.1 -> "12,1 %" (id, non-breaking space) or "12.1%" (en)."""
        return self.t("format.percent", value=self.number(value, decimals))

    @staticmethod
    def date(day: date) -> str:
        """Format a date as ISO 8601 ("2026-11-04") in every language."""
        return day.isoformat()[:10]

    def month(self, number: int) -> str:
        """Translated short month name (1-12), e.g. "Agu" / "Aug"."""
        return self.t(f"month.short.{number}")

    def category(self, label: str) -> str:
        """Translated name of a US AQI category given its English EPA label."""
        return self.t(category_key(label))

    def season(self, label: str) -> str:
        """Translated name of a season given its data label ("Dry" or "Wet")."""
        return self.t(f"season.{label}")

    def feature(self, column: str) -> str:
        """Translated display label of a variable or model feature; the CAMS regime flags
        name their upgrade month, e.g. "(Nov 2024)"."""
        if column in CAMS_UPGRADES:
            year, month, _ = CAMS_UPGRADES[column].split("-")
            return self.t(f"feature.{column}", month=self.month(int(month)), year=year)
        return self.t(f"feature.{column}")
