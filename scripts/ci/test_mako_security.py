"""Keep patched Mako in release images and published base requirements."""

from pathlib import Path

import tomllib
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]


def test_published_base_requires_patched_mako_without_workspace_overrides() -> None:
    """Require an unconditional patched floor in the published package metadata."""
    project = tomllib.loads((ROOT / "src/backend/base/pyproject.toml").read_text())["project"]
    requirement = next(
        requirement for value in project["dependencies"] if (requirement := Requirement(value)).name == "mako"
    )
    assert requirement.marker is None
    assert any(bound.operator == ">=" and Version(bound.version) >= Version("1.4.2") for bound in requirement.specifier)
    assert "1.4.1" not in requirement.specifier
    assert "1.4.2" in requirement.specifier
    assert "2.0.0" not in requirement.specifier


def test_release_lock_resolves_patched_mako() -> None:
    """Keep every locked Mako resolution at or above the patched release."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    packages = [package for package in lock["package"] if package["name"] == "mako"]
    assert packages
    assert all(Version(package["version"]) >= Version("1.4.2") for package in packages)
