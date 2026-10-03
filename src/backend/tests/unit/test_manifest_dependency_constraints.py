"""Regression tests for constraints on dependencies reported in issue #15359."""

from __future__ import annotations

import sys
from pathlib import Path

from packaging.requirements import Requirement

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_pyproject(relative_path: str) -> dict:
    with (REPO_ROOT / relative_path).open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)


def _requirement(requirements: list[str], name: str) -> Requirement:
    matches = [requirement for spec in requirements if (requirement := Requirement(spec)).name == name]
    assert len(matches) == 1, f"Expected one {name} requirement, found {matches}"
    return matches[0]


def test_litellm_extra_reuses_cryptography_security_floor() -> None:
    extras = _load_pyproject("src/backend/base/pyproject.toml")["project"]["optional-dependencies"]

    assert _requirement(extras["litellm"], "cryptography") == Requirement("cryptography>=50.0.0")


def test_stepflow_requires_compatible_lfx() -> None:
    dependencies = _load_pyproject("src/langflow-stepflow/pyproject.toml")["project"]["dependencies"]

    assert _requirement(dependencies, "lfx") == Requirement("lfx>=1.13.0.dev0,<2.0.0")


def test_gp_script_dependencies_are_major_bounded() -> None:
    requirements_path = REPO_ROOT / "scripts" / "gp" / "requirements.txt"
    requirements = {Requirement(line).name: Requirement(line) for line in requirements_path.read_text().splitlines()}

    assert requirements == {
        "requests": Requirement("requests>=2.33.0,<3.0.0"),
        "python-dotenv": Requirement("python-dotenv>=1.0.0,<2.0.0"),
    }
