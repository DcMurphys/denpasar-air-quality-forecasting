"""Shared constants for the notebook and the dashboard.

Values are copied from the notebook configuration cell (NB §3.2). Kaggle input paths stay in the
notebook; output paths follow the repository layout (scope §9, item 8).
"""

import calendar
import math
from pathlib import Path

# ===== Reproducibility =====
SEED = 126

# ===== Repository paths (editable install: src/aqi_forecasting -> repository root) =====
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
MODEL_DIR = ARTIFACT_DIR / "trained_models"
FIG_DIR = PROJECT_ROOT / "reports" / "figures"
TUNING_DIR = PROJECT_ROOT / "reports" / "tuning"

# ===== Scope and join keys =====
CITY = "Denpasar"
ID_COLS = ("city", "province", "island")
MERGE_KEYS = [*ID_COLS, "date"]
HOURLY_POLLUTANTS = [
    "carbon_monoxide",
    "nitrogen_dioxide",
    "sulphur_dioxide",
    "ozone",
    "dust",
    "uv_index",
]

# ===== Targets =====
TARGET = "us_aqi_mean"
RAW_TARGET_COLS = ["us_aqi_mean", "us_aqi_max"]  # daily AQI columns imputed after the merge
MAX_TARGET_GAP_DAYS = 3  # longest interior gap filled by interpolation
TARGET_NEXT_DAY = "us_aqi_mean_t+1"  # EDA only: next-day AQI
HORIZON = 7  # forecast days t+1 ... t+7
TARGET_COLS = [f"aqi_t+{h}" for h in range(1, HORIZON + 1)]

# ===== Feature catalogue (column -> display label, English; the dashboard uses locales) =====
WEATHER_FEATURES: dict[str, str] = {
    "temperature_2m_mean": "Average temperature (°C)",
    "precipitation_sum": "Rain precipitation (mm)",
    "precipitation_hours": "Rain duration (hours)",
    "wind_speed_10m_max": "Maximum of wind speed (km/h)",
    "shortwave_radiation_sum": "Shortwave radiation (MJ/m²)",
}
POLLUTANT_FEATURES: dict[str, str] = {
    "pm2_5_mean": "PM2.5 (µg/m³)",
    "pm10_mean": "PM10 (µg/m³)",
    "carbon_monoxide_mean": "CO (µg/m³)",
    "nitrogen_dioxide_mean": "NO₂ (µg/m³)",
    "sulphur_dioxide_mean": "SO₂ (µg/m³)",
    "ozone_mean": "O₃ (µg/m³)",
    "dust_mean": "Dust (µg/m³)",
}
# Model inputs. The order is explicit because tree ensembles and the redundancy filter are
# sensitive to column order; dust_mean is excluded because it is near zero since 2023 (see EDA).
POLLUTANT_COLS = [
    "pm2_5_mean",
    "pm10_mean",
    "ozone_mean",
    "nitrogen_dioxide_mean",
    "sulphur_dioxide_mean",
    "carbon_monoxide_mean",
]
WEATHER_COLS = [
    "precipitation_sum",
    "precipitation_hours",
    "wind_speed_10m_max",
    "shortwave_radiation_sum",
    "temperature_2m_mean",
]

# ===== Calendar, seasons, and CAMS model regimes =====
DAYS_PER_YEAR = 365.25
MONTH_LABELS = list(calendar.month_abbr)[1:]
WET_SEASON_MONTHS = (11, 12, 1, 2, 3)
CAMS_UPGRADES = {"post_cams_49r1": "2024-11-12", "post_cams_50r1": "2026-05-12"}
MODEL_REGIME_FLAGS = ["post_cams_49r1"]  # 50r1 occurs only in the test period: evaluation only

# ===== US EPA AQI categories: (label, upper bound, colour) =====
AQI_CATEGORIES: tuple[tuple[str, float, str], ...] = (
    ("Good", 50, "#00e400"),
    ("Moderate", 100, "#ffff00"),
    ("Unhealthy for Sensitive Groups", 150, "#ff7e00"),
    ("Unhealthy", 200, "#ff0000"),
    ("Very Unhealthy", 300, "#8f3f97"),
    ("Hazardous", math.inf, "#7e0023"),
)
AQI_LABELS = [label for label, _, _ in AQI_CATEGORIES]
AQI_COLORS = [color for _, _, color in AQI_CATEGORIES]
AQI_BINS = [0, *(upper for _, upper, _ in AQI_CATEGORIES)]

# ===== WHO guideline (not in the notebook) =====
# WHO 2021 24-hour PM2.5 guideline. The raw-data flag `exceeds_who_pm25` equals
# `pm2_5_mean > 15` on every row (scope §5.1, decision Q6).
WHO_PM25_24H_GUIDELINE = 15.0

# ===== Plot palette and export =====
COLOR_PRED, COLOR_MUTED = "#2a78d6", "#8a8984"
FIG_DPI = 150

# ===== EDA and statistical tests =====
TREND_ROLLING_WINDOW = 30  # days, for trend smoothing in line charts
ALPHA = 0.05
N_HARMONICS = 2  # annual Fourier harmonics (seasonal analysis and calendar features)
ZA_TRIM = 0.05  # Zivot–Andrews: searches breaks closer to the sample ends than 0.15

# ===== Feature engineering =====
AQI_LAGS = (1, 2)
ROLLING_WINDOWS = (7, 30)
ROLLING_STATS = ("mean", "max", "std")
RAIN_SUM_WINDOWS = (3, 7)
MAX_FFILL_DAYS = 3

# ===== Split, feature selection, and cross-validation =====
SPLIT_RATIOS = {"train": 0.65, "val": 0.15, "test": 0.20}
EMBARGO = HORIZON - 1  # rows dropped between splits so multi-day targets never overlap
CORR_THRESHOLD = 0.95
CV_SPLITS = 10

# ===== Modelling, evaluation, and forecasting =====
N_TRIALS = 30
SMAPE_TARGET = 15.0  # success criterion: test sMAPE (%), mean over horizons
EVAL_SPLIT = "test"
HISTORY_DAYS = 60  # days of history shown in the forecast chart
