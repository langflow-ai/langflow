"""Regression tests for security dependency floors in published package metadata."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_pyproject(relative_path: str) -> dict:
    with (REPO_ROOT / relative_path).open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)


def _requirement(requirements: list[str], name: str) -> Requirement:
    matches = [requirement for spec in requirements if (requirement := Requirement(spec)).name.lower() == name.lower()]
    assert len(matches) == 1, f"Expected one {name} requirement, found {matches}"
    assert matches[0].marker is None, f"Security floor for {name} must be unconditional"
    return matches[0]


def _assert_specifier(requirement: Requirement, operator: str, version: str) -> None:
    assert any(spec.operator == operator and spec.version == version for spec in requirement.specifier), requirement


def _assert_floor(requirement: Requirement, version: str) -> None:
    floor = Version(version)
    assert any(
        specifier.operator == ">=" and Version(specifier.version) >= floor for specifier in requirement.specifier
    ), requirement


def test_workspace_security_overrides_enforce_patched_versions() -> None:
    overrides = _load_pyproject("pyproject.toml")["tool"]["uv"]["override-dependencies"]

    gitpython = _requirement(overrides, "GitPython")
    _assert_floor(gitpython, "3.1.58")

    pypdf = _requirement(overrides, "pypdf")
    _assert_floor(pypdf, "6.15.0")
    _assert_specifier(pypdf, "<", "7.0.0")

    h2 = _requirement(overrides, "h2")
    _assert_floor(h2, "4.4.1")


def test_published_packages_enforce_patched_h2_floor() -> None:
    for relative_path in (
        "src/backend/base/pyproject.toml",
        "src/lfx/pyproject.toml",
        "src/sdk/pyproject.toml",
    ):
        dependencies = _load_pyproject(relative_path)["project"]["dependencies"]
        _assert_floor(_requirement(dependencies, "h2"), "4.4.1")


def test_published_packages_enforce_patched_pypdf_floor() -> None:
    for relative_path in ("src/backend/base/pyproject.toml", "src/lfx/pyproject.toml"):
        dependencies = _load_pyproject(relative_path)["project"]["dependencies"]
        pypdf = _requirement(dependencies, "pypdf")
        _assert_floor(pypdf, "6.15.0")
        _assert_specifier(pypdf, "<", "7.0.0")

    base_extras = _load_pyproject("src/backend/base/pyproject.toml")["project"]["optional-dependencies"]
    pypdf_extra = _requirement(base_extras["pypdf"], "pypdf")
    _assert_floor(pypdf_extra, "6.15.0")
    _assert_specifier(pypdf_extra, "<", "7.0.0")


def test_published_extras_enforce_patched_gitpython_floor() -> None:
    base_extras = _load_pyproject("src/backend/base/pyproject.toml")["project"]["optional-dependencies"]
    _assert_floor(_requirement(base_extras["gitpython"], "GitPython"), "3.1.58")

    bundle_extras = _load_pyproject("src/bundles/lfx-bundles/pyproject.toml")["project"]["optional-dependencies"]
    _assert_floor(_requirement(bundle_extras["git"], "GitPython"), "3.1.58")

    generator = runpy.run_path(str(REPO_ROOT / "scripts/migrate/consolidate_bundles.py"))
    assert generator["PROVIDER_DEPS"]["git"] == bundle_extras["git"]
