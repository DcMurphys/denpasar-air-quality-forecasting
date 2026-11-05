"""Guards for dashboard/requirements.txt, the dependency file Streamlit Community Cloud reads."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOUD_REQUIREMENTS = ROOT / "dashboard" / "requirements.txt"


def _requirement_lines(path: Path) -> list[str]:
    lines = (line.split("#", 1)[0].strip() for line in path.read_text().splitlines())
    return [line for line in lines if line]


def _pins(path: Path) -> dict[str, str]:
    pins = {}
    for line in _requirement_lines(path):
        name, _, version = line.partition("==")
        pins[name.strip().lower()] = version.strip()
    return pins


def test_cloud_requirements_are_plain_pins() -> None:
    for line in _requirement_lines(CLOUD_REQUIREMENTS):
        assert re.fullmatch(r"[A-Za-z0-9_.\-]+==[\w.]+", line), f"not an exact pin: {line!r}"


def test_cloud_requirements_skip_the_model_library() -> None:
    assert "scikit-learn" not in _pins(CLOUD_REQUIREMENTS)


def test_no_competing_dependency_file_next_to_the_entrypoint() -> None:
    competing = ["uv.lock", "Pipfile", "environment.yml", "pyproject.toml"]
    assert [name for name in competing if (ROOT / "dashboard" / name).exists()] == []


def test_cloud_pins_match_environment_yml() -> None:
    conda_pins = dict(
        re.findall(r"^\s*-\s*([a-z0-9_\-]+)=([\d.]+)", (ROOT / "environment.yml").read_text(), re.M)
    )
    cloud = _pins(CLOUD_REQUIREMENTS)
    for name in ("pandas", "numpy"):
        assert cloud[name] == conda_pins[name], name


def test_root_requirements_include_the_cloud_file() -> None:
    assert "-r dashboard/requirements.txt" in _requirement_lines(ROOT / "requirements.txt")
