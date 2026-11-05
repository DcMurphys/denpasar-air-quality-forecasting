"""CSV downloads for expert users (UX priority 8).

Files keep the original column names and a decimal point, so they open the same way in Excel,
Python, or R regardless of the dashboard language.
"""

import pandas as pd
import streamlit as st

from dashboard.views.i18n import Translator


def csv_download(tr: Translator, frame: pd.DataFrame, file_name: str, key: str) -> None:
    st.download_button(
        tr.t("download.csv"),
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
        icon=":material/download:",
        help=tr.t("download.help"),
        key=key,
        on_click="ignore",  # downloading must not rerun the app
    )
