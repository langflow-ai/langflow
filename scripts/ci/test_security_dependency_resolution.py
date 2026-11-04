"""Keep fixed image dependencies compatible across supported Python versions."""

from __future__ import annotations

from pathlib import Path

import pytest
import tomllib
from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = [
    "src/backend/base/pyproject.toml",
    "src/lfx/pyproject.toml",
    "src/bundles/nextplaid/pyproject.toml",
]


def locked_packages(environment: dict[str, str]) -> dict[str, str]:
    """Select one locked package version for each dependency in an environment."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    packages = {}
    for package in lock["package"]:
        markers = package.get("resolution-markers", [])
        if markers and not any(Marker(value).evaluate(environment) for value in markers):
            continue
        assert package["name"] not in packages, f"ambiguous lock resolution for {package['name']}"
        packages[package["name"]] = package["version"]
    return packages


@pytest.mark.parametrize("python", ["3.10", "3.11", "3.14"])
@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
def test_fixed_dependencies_resolve_on_every_supported_python_line(python: str, platform: str) -> None:
    """Check patched versions while retaining compatible Python 3.10 resolutions."""
    environment = {
        "python_version": python,
        "python_full_version": f"{python}.0",
        "sys_platform": platform,
        "platform_machine": "aarch64" if platform == "linux" else "arm64",
    }
    packages = locked_packages(environment)
    for relative_path in MANIFESTS:
        project = tomllib.loads((ROOT / relative_path).read_text())["project"]
        for name in ("pillow", "filelock"):
            requirements = [
                requirement
                for value in project["dependencies"]
                if (requirement := Requirement(value)).name == name
                and (requirement.marker is None or requirement.marker.evaluate(environment))
            ]
            if relative_path.endswith("nextplaid/pyproject.toml") and name == "filelock":
                continue
            assert len(requirements) == 1, f"{relative_path}: {name} must resolve exactly once on {python}"
            assert packages[name] in requirements[0].specifier
    if python == "3.10":
        assert Version(packages["pillow"]).major == 12
        assert Version(packages["filelock"]) < Version("4.2")
    else:
        assert Version(packages["pillow"]) >= Version("13.0.0")
        assert Version(packages["filelock"]) >= Version("4.2.1")
    assert Version(packages["pypdf"]) >= Version("6.21.2")
    assert Version(packages["aiohttp"]) >= Version("3.14.4")
    assert Version(packages["mako"]) >= Version("1.4.2")

    for name, minimum in {
        "black": "26.10.1",
        "certifi": "2026.10.18",
        "docling-core": "2.103.0",
        "joserfc": "1.7.6",
        "langgraph": "1.2.15",
        "mem0ai": "2.0.18",
        "msgpack": "1.2.3",
        "nltk": "3.10.4",
        "pyasn1": "0.6.5",
        "pymongo": "4.18.3",
        "setuptools": "84.1.0",
    }.items():
        assert Version(packages[name]) >= Version(minimum), name

    # Upstream fixes require Python 3.11. Keep the 3.10 runtime installable;
    # these three findings remain open for that runtime.
    if python != "3.10":
        for name, minimum in {"dnspython": "2.9.0", "locust": "2.47.0", "pyarrow": "26.0.0"}.items():
            assert Version(packages[name]) >= Version(minimum), name


def test_opentelemetry_lock_updates_the_whole_official_release_set() -> None:
    """Keep the stable and instrumentation packages on compatible patched releases."""
    packages = locked_packages({"python_version": "3.14", "python_full_version": "3.14.0", "sys_platform": "linux"})
    stable = {
        version
        for name, version in packages.items()
        if name.startswith("opentelemetry-")
        and (
            name in {"opentelemetry-api", "opentelemetry-sdk", "opentelemetry-proto"}
            or name.startswith("opentelemetry-exporter-otlp")
        )
        and Version(version).major == 1
    }
    assert len(stable) == 1
    assert Version(stable.pop()) >= Version("1.45.1")
    conventions = packages["opentelemetry-semantic-conventions"]
    for name in (
        "opentelemetry-instrumentation",
        "opentelemetry-util-http",
        "opentelemetry-exporter-prometheus",
        "opentelemetry-instrumentation-fastapi",
        "opentelemetry-instrumentation-asgi",
        "opentelemetry-instrumentation-sqlalchemy",
        "opentelemetry-instrumentation-requests",
        "opentelemetry-instrumentation-urllib3",
        "opentelemetry-instrumentation-system-metrics",
    ):
        assert packages[name] == conventions
    assert Version(conventions) >= Version("0.66b1")


@pytest.mark.parametrize("manifest", MANIFESTS[:2])
def test_published_requirements_reject_vulnerable_aiohttp_without_workspace_constraints(manifest: str) -> None:
    """Apply the aiohttp security floor to published packages without workspace rules."""
    project = tomllib.loads((ROOT / manifest).read_text())["project"]
    requirement = next(
        requirement for value in project["dependencies"] if (requirement := Requirement(value)).name == "aiohttp"
    )
    assert requirement.marker is None
    assert "3.14.3" not in requirement.specifier
    assert "3.14.4" in requirement.specifier


def test_published_base_requirements_reject_vulnerable_mako_without_workspace_overrides() -> None:
    """Reject vulnerable Mako ranges in the published base package requirements."""
    project = tomllib.loads((ROOT / MANIFESTS[0]).read_text())["project"]
    requirement = next(
        requirement for value in project["dependencies"] if (requirement := Requirement(value)).name == "mako"
    )
    assert requirement.marker is None
    assert any(bound.operator == ">=" and Version(bound.version) >= Version("1.4.2") for bound in requirement.specifier)
    assert "1.4.1" not in requirement.specifier
    assert "1.4.2" in requirement.specifier
    assert "2.0.0" not in requirement.specifier
