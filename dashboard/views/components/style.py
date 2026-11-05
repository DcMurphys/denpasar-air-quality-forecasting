"""Global readability styles (UX review, priority 3).

Streamlit renders captions at 14 px with 60 % opacity (about 4.9:1 contrast) and controls at
32 px. These rules raise captions to 15.2 px at 9.7:1 and give controls a 44 px touch target,
for older users and anyone on a small screen.
"""

import streamlit as st

from dashboard.views.components.palette import SECONDARY_TEXT

_CSS = f"""
<style>
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {{
  opacity: 1 !important;
  color: {SECONDARY_TEXT} !important;
  font-size: 0.95rem !important;
  line-height: 1.5 !important;
}}
[data-testid="stButtonGroup"] button,
[data-testid="stDownloadButton"] button,
button[data-baseweb="tab"],
[data-testid="stPageLink"] a,
[data-testid="stExpander"] summary {{
  min-height: 44px !important;
}}
[data-testid="stPageLink"] a {{
  display: flex;
  align-items: center;
}}
/* Phones: Streamlit pads table headers 16 px on the left and never wraps cells, which pushed
   the annual and monthly tables past 375 px (M13). */
@media (max-width: 640px) {{
  [data-testid="stTable"] th, [data-testid="stTable"] td {{
    padding-left: 0.35rem !important;
    padding-right: 0.35rem !important;
  }}
}}
</style>
"""


def inject_global_css() -> None:
    st.html(_CSS)
