"""Data and method sources shown in the sidebar (UX priority 6).

URLs come from the notebook: CAMS (NB §4), the Kaggle dataset paths (NB §3.2), and the WHO 2021
guideline (NB §1.1 references); the US EPA AQI page is the scale used throughout the app.
"""

from dashboard.views.i18n import Translator

CAMS_URL = "https://atmosphere.copernicus.eu/"
KAGGLE_AQ_URL = "https://www.kaggle.com/datasets/danielaijdkx/indonesia-air-quality-hourly-pm25"
KAGGLE_WEATHER_URL = (
    "https://www.kaggle.com/datasets/danielaijdkx/indonesia-daily-weather-31-cities"
)
EPA_AQI_URL = "https://www.airnow.gov/aqi/aqi-basics/"
WHO_AQG_URL = "https://www.who.int/publications/i/item/9789240034228"


def sources_markdown(tr: Translator) -> str:
    """One translated sentence with Markdown links to every source."""
    return tr.t(
        "sidebar.sources",
        cams=f"[Copernicus CAMS]({CAMS_URL})",
        aq=f"[{tr.t('sidebar.sources.aq')}]({KAGGLE_AQ_URL})",
        weather=f"[{tr.t('sidebar.sources.weather')}]({KAGGLE_WEATHER_URL})",
        epa=f"[US EPA AQI]({EPA_AQI_URL})",
        who=f"[WHO 2021]({WHO_AQG_URL})",
    )
