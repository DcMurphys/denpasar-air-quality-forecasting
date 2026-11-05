"""Tridatu UI palette (white, red, black). Keep in sync with .streamlit/config.toml.

These colours are for interface chrome only; AQI categories keep the US EPA colours.
"""

from pathlib import Path

WHITE = "#FFFFFF"
BLACK = "#111111"
RED = "#D7192D"  # 5.2:1 on white; used for accents, icons, and borders
RED_TINT = "#FDECEE"  # info callout background (black text on it: 16.6:1)
MUTED_TEXT = "#555555"  # 7.5:1 on white
SECONDARY_TEXT = "#444444"  # captions, 9.7:1 on white
BORDER = "#D9D9D9"

ASSET_DIR = Path(__file__).resolve().parents[2] / "assets"
# Bunga jepun sidebar figure: the owner's jepun_fixed.svg (2026-11-04, 7.2 MB with embedded PNG
# layers) rendered to a 280 px PNG (66 KB), twice its 140 px display width. The background is
# opaque white, matching the white sidebar of the fixed light theme.
JEPUN_IMAGE = ASSET_DIR / "jepun.png"
JEPUN_ICON_SVG = ASSET_DIR / "jepun_icon.svg"  # single blossom for the browser tab
