"""Regression tests for CLI dependency floors in published package metadata."""

from __future__ import annotations

import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[4]
TYPER_LITERAL_FLOOR = Version("0.19.0")


def test_langflow_base_requires_typer_with_literal_option_support() -> None:
    """Every valid langflow-base install must support Literal CLI annotations."""
    with (REPO_ROOT / "src/backend/base/pyproject.toml").open("rb") as pyproject_file:
        dependencies = tomllib.load(pyproject_file)["project"]["dependencies"]

    matches = [requirement for spec in dependencies if (requirement := Requirement(spec)).name == "typer"]

    assert len(matches) == 1
    assert any(
        specifier.operator == ">=" and Version(specifier.version) >= TYPER_LITERAL_FLOOR
        for specifier in matches[0].specifier
    ), matches[0]
