"""Entry point. Run from the repository root:

conda run -n lab_venv --no-capture-output streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

# `streamlit run` only puts dashboard/ on sys.path; the `dashboard` package needs the repo root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.controllers.shell import run  # noqa: E402

run()
