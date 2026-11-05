"""Entry point. Run from the repository root:

conda run -n lab_venv --no-capture-output streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

# `streamlit run` only puts dashboard/ on sys.path. The `dashboard` package needs the repo root,
# and `aqi_forecasting` needs src/. Adding src/ here means the app runs without `pip install -e .`
# (Streamlit Community Cloud does not document support for local-path installs).
ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dashboard.controllers.shell import run  # noqa: E402

run()
