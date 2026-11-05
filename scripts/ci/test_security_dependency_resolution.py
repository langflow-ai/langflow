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
    assert Version(packages["brotli"]) >= Version("1.2.1")
    assert Version(packages["brotlicffi"]) >= Version("1.2.1.0")
    for name, minimum in {"joserfc": "1.7.6", "pyasn1": "0.6.5", "pymongo": "4.18.3", "setuptools": "84.1.0"}.items():
        assert Version(packages[name]) >= Version(minimum), name
    if python != "3.10":
        assert Version(packages["dnspython"]) >= Version("2.9.1")
        assert Version(packages["pyarrow"]) >= Version("26.0.1")


def test_opentelemetry_lock_updates_the_whole_official_release_set() -> None:
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
    project = tomllib.loads((ROOT / manifest).read_text())["project"]
    requirement = next(
        requirement for value in project["dependencies"] if (requirement := Requirement(value)).name == "aiohttp"
    )
    assert requirement.marker is None
    assert "3.14.3" not in requirement.specifier
    assert "3.14.4" in requirement.specifier


@pytest.mark.parametrize(
    ("manifest", "extra"),
    [("src/backend/base/pyproject.toml", "duckduckgo"), ("src/bundles/duckduckgo/pyproject.toml", None)],
)
@pytest.mark.parametrize(
    ("implementation", "dependency", "affected", "fixed"),
    [("CPython", "brotli", "1.2.0", "1.2.1"), ("PyPy", "brotlicffi", "1.2.0.1", "1.2.1.0")],
)
def test_published_duckduckgo_requires_patched_decoder(
    manifest: str, extra: str | None, implementation: str, dependency: str, affected: str, fixed: str
) -> None:
    """Protect published installs through the decoder selected by HTTPX."""
    project = tomllib.loads((ROOT / manifest).read_text())["project"]
    declarations = project["optional-dependencies"][extra] if extra else project["dependencies"]
    environment = {"platform_python_implementation": implementation, "python_version": "3.14"}
    requirements = [
        requirement
        for value in declarations
        if (requirement := Requirement(value)).name.lower() == dependency
        and (requirement.marker is None or requirement.marker.evaluate(environment))
    ]
    assert len(requirements) == 1
    assert affected not in requirements[0].specifier
    assert fixed in requirements[0].specifier


@pytest.mark.parametrize("manifest", ["src/backend/base/pyproject.toml", "src/bundles/confluent/pyproject.toml"])
@pytest.mark.parametrize("python", ["3.10", "3.11", "3.14"])
def test_published_pyarrow_floor_keeps_supported_python_lines(manifest: str, python: str) -> None:
    """Require patched Arrow where available without dropping Python 3.10."""
    project = tomllib.loads((ROOT / manifest).read_text())["project"]
    requirements = [
        requirement
        for value in project["dependencies"]
        if (requirement := Requirement(value)).name.lower() == "pyarrow"
        and (requirement.marker is None or requirement.marker.evaluate({"python_version": python}))
    ]
    if python == "3.10":
        assert all("23.0.1" in requirement.specifier for requirement in requirements)
    else:
        assert len(requirements) == 1
        assert "26.0.0" not in requirements[0].specifier
        assert "26.0.1" in requirements[0].specifier


@pytest.mark.parametrize(
    ("dependency", "affected", "patched", "next_major"),
    [("dnspython", "2.9.0", "2.9.1", "3.0.0"), ("joserfc", "1.7.5", "1.7.6", "2.0.0")],
)
@pytest.mark.parametrize("python", ["3.10", "3.11", "3.14"])
def test_plain_base_requirements_protect_dns_and_jose_transitive_paths(
    dependency: str, affected: str, patched: str, next_major: str, python: str
) -> None:
    """Publish mandatory-path security floors while preserving Python 3.10 support."""
    project = tomllib.loads((ROOT / MANIFESTS[0]).read_text())["project"]
    requirements = [
        requirement
        for value in project["dependencies"]
        if (requirement := Requirement(value)).name == dependency
        and (requirement.marker is None or requirement.marker.evaluate({"python_version": python}))
    ]
    if dependency == "dnspython" and python == "3.10":
        assert not requirements
    else:
        assert len(requirements) == 1
        assert affected not in requirements[0].specifier
        assert patched in requirements[0].specifier
        assert next_major not in requirements[0].specifier
