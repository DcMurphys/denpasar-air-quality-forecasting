"""MVC dependency rules (scope §6): models never import streamlit or the views layer."""

import ast
from pathlib import Path

import pytest

DASHBOARD_MODELS = Path(__file__).resolve().parents[1] / "dashboard" / "models"


def _imported_modules(path: Path) -> set[str]:
    """Return the full module names imported by a Python file."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("path", sorted(DASHBOARD_MODELS.rglob("*.py")), ids=lambda p: p.name)
def test_models_do_not_import_streamlit_or_views(path: Path) -> None:
    for module in _imported_modules(path):
        assert module.split(".")[0] != "streamlit", (path, module)
        assert not module.startswith("dashboard.views"), (path, module)
        assert not module.startswith("dashboard.controllers"), (path, module)
