"""Forecast helpers (scope §4.3). Days 1–3 are actionable; days 4–7 are an outlook (NB §7.10)."""

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from aqi_forecasting.config import AQI_LABELS, HISTORY_DAYS, TARGET

ACTIONABLE_DAYS = 3
# History windows for the forecast chart: a short default so the 7 forecast days stay legible,
# and the notebook's 60 days (NB §3.2 HISTORY_DAYS) on request (owner decision, M9).
SHORT_HISTORY_DAYS = 14
HISTORY_WINDOWS = (SHORT_HISTORY_DAYS, HISTORY_DAYS)

# Two-tier early-warning rule (NB §9.5): AQI threshold, and the dry-and-calm conditions of
# Tier 2. "No rain" means under 1 mm on each day (decision Q8).
ADVISORY_AQI = 100
DRY_DAYS = 3
NO_RAIN_MM = 1.0
CALM_WIND_KMH = 15


def issue_date(daily: pd.DataFrame) -> pd.Timestamp:
    """The forecast is issued from the last observed day of ``dashboard_daily``."""
    return daily.index[-1]


def history(daily: pd.DataFrame, days: int = HISTORY_DAYS) -> pd.DataFrame:
    """The last ``days`` observed days (date, aqi) shown before the forecast (NB §8.2)."""
    tail = daily[TARGET].tail(days)
    return pd.DataFrame({"date": tail.index, "aqi": tail.to_numpy()})


@dataclass(frozen=True)
class Advisory:
    """Indicative status of the two-tier early-warning rule (NB §9.5) for an analyst to confirm.

    Tier 1: the forecast or its P90 band exceeds AQI 100 within days 1-3.
    Tier 2: Tier 1 on a dry (no rain for ``DRY_DAYS`` days) and calm (wind below
    ``CALM_WIND_KMH``) last observed day.
    """

    tier1: bool
    trigger_days: tuple[int, ...]  # horizons (1-3) whose forecast or P90 exceeds AQI 100
    max_high: float  # highest P90 upper band over days 1-3
    dry: bool  # every one of the last DRY_DAYS days had under NO_RAIN_MM of rain
    max_recent_rain: float  # wettest of those days, mm
    calm: bool
    last_wind: float  # km/h on the last observed day

    @property
    def tier2(self) -> bool:
        return self.tier1 and self.dry and self.calm

    @property
    def level(self) -> str:
        return "tier2" if self.tier2 else "tier1" if self.tier1 else "none"


def advisory(forecast: pd.DataFrame, daily: pd.DataFrame) -> Advisory:
    actionable = forecast.loc[forecast["horizon"] <= ACTIONABLE_DAYS]
    exceeds = (actionable["aqi_pred"] > ADVISORY_AQI) | (actionable["aqi_high"] > ADVISORY_AQI)
    recent_rain = daily["precipitation_sum"].tail(DRY_DAYS)
    last_wind = float(daily["wind_speed_10m_max"].iloc[-1])
    return Advisory(
        tier1=bool(exceeds.any()),
        trigger_days=tuple(int(h) for h in actionable.loc[exceeds, "horizon"]),
        max_high=float(actionable["aqi_high"].max()),
        dry=bool((recent_rain < NO_RAIN_MM).all()),
        max_recent_rain=float(recent_rain.max()),
        calm=last_wind < CALM_WIND_KMH,
        last_wind=last_wind,
    )


# ===== Today and tomorrow (UX review, priority 1) =====
DENPASAR_TZ = ZoneInfo("Asia/Makassar")  # WITA, UTC+8
OBSERVED, FORECAST, OUTLOOK, UNAVAILABLE = "observed", "forecast", "outlook", "unavailable"


def local_today(now: datetime | None = None) -> date:
    """Today's date in Denpasar, whatever the server's time zone."""
    return (now or datetime.now(DENPASAR_TZ)).astimezone(DENPASAR_TZ).date()


def data_age_days(daily: pd.DataFrame, today: date) -> int:
    """Whole days between the last observed day and ``today`` (0 when data is from today)."""
    return (today - issue_date(daily).date()).days


@dataclass(frozen=True)
class DayOutlook:
    """The AQI to show for one calendar day, and where it comes from.

    ``source`` is ``observed`` (the day is in the data), ``forecast`` (days 1-3, actionable),
    ``outlook`` (days 4-7, indicative only), or ``unavailable`` (outside the forecast window).
    """

    day: date
    source: str
    horizon: int | None = None
    aqi: float | None = None
    aqi_low: float | None = None
    aqi_high: float | None = None
    category: str | None = None

    @property
    def is_sensitive_risk(self) -> bool:
        """True from "Unhealthy for Sensitive Groups" upwards (index 2 of the EPA scale)."""
        return self.category is not None and AQI_LABELS.index(self.category) >= 2


def day_outlook(daily: pd.DataFrame, forecast: pd.DataFrame | None, day: date) -> DayOutlook:
    """Observed AQI if ``day`` is in the data, else its forecast row, else unavailable."""
    stamp = pd.Timestamp(day)
    if stamp in daily.index:
        row = daily.loc[stamp]
        return DayOutlook(day, OBSERVED, aqi=float(row[TARGET]), category=str(row["aqi_category"]))
    if forecast is not None:
        match = forecast.loc[forecast["date"] == stamp]
        if len(match):
            row = match.iloc[0]
            horizon = int(row["horizon"])
            return DayOutlook(
                day,
                FORECAST if horizon <= ACTIONABLE_DAYS else OUTLOOK,
                horizon=horizon,
                aqi=float(row["aqi_pred"]),
                aqi_low=float(row["aqi_low"]),
                aqi_high=float(row["aqi_high"]),
                category=str(row["category"]),
            )
    return DayOutlook(day, UNAVAILABLE)


def relative_day(day: date, today: date) -> str:
    """``past``, ``today``, ``tomorrow``, or ``later`` relative to ``today``."""
    delta = (pd.Timestamp(day).date() - today).days  # accepts dates and Timestamps
    return "past" if delta < 0 else "today" if delta == 0 else "tomorrow" if delta == 1 else "later"
