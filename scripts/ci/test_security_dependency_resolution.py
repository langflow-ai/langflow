"""Keep fixed image dependencies compatible across supported Python versions."""

from __future__ import annotations

import json
import runpy
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
    assert Version(packages["brotli"]) >= Version("1.2.1")
    assert Version(packages["brotlicffi"]) >= Version("1.2.1.0")
    assert Version(packages["mako"]) >= Version("1.4.2")

    for name, minimum in {
        "black": "26.10.1",
        "certifi": "2026.10.19",
        "docling-core": "2.103.0",
        "fastmcp": "3.4.10",
        "fastmcp-slim": "3.4.10",
        "gitpython": "3.2.1",
        "joserfc": "1.7.6",
        "langchain-nvidia-ai-endpoints": "1.5.0",
        "langgraph": "1.2.15",
        "litellm": "1.103.10",
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
        for name, minimum in {"dnspython": "2.9.1", "locust": "2.47.0", "pyarrow": "26.0.1"}.items():
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


@pytest.mark.parametrize(
    ("manifest", "dependency", "affected", "patched"),
    [
        ("src/backend/base/pyproject.toml", "litellm", "1.103.2", "1.103.10"),
        ("src/bundles/toolguard/pyproject.toml", "litellm", "1.103.2", "1.103.10"),
        ("src/bundles/lfx-bundles/pyproject.toml", "litellm", "1.103.2", "1.103.10"),
        ("src/backend/base/pyproject.toml", "gitpython", "3.2.0", "3.2.1"),
        ("src/bundles/lfx-bundles/pyproject.toml", "gitpython", "3.2.0", "3.2.1"),
        ("src/backend/base/pyproject.toml", "fastmcp", "3.4.4", "3.4.10"),
        ("src/bundles/toolguard/pyproject.toml", "fastmcp", "3.4.4", "3.4.10"),
        ("src/backend/base/pyproject.toml", "langchain-nvidia-ai-endpoints", "1.0.4", "1.5.0"),
        ("src/bundles/lfx-bundles/pyproject.toml", "langchain-nvidia-ai-endpoints", "1.0.4", "1.5.0"),
    ],
)
def test_published_security_floors_reject_affected_versions(
    manifest: str, dependency: str, affected: str, patched: str
) -> None:
    """Protect fresh wheel installs without relying on the workspace lockfile."""
    project = tomllib.loads((ROOT / manifest).read_text())["project"]
    declarations = project.get("dependencies", []) + [
        value for values in project.get("optional-dependencies", {}).values() for value in values
    ]
    requirements = [
        requirement for value in declarations if (requirement := Requirement(value)).name.lower() == dependency
    ]
    assert requirements, f"{manifest} must declare its {dependency} security floor"
    for requirement in requirements:
        assert affected not in requirement.specifier, str(requirement)
        assert patched in requirement.specifier, str(requirement)
        if dependency == "litellm":
            assert "1.104.0rc1" not in requirement.specifier
            assert "1.107.0" not in requirement.specifier
            for affected_branch in ("1.104.7", "1.105.5", "1.106.4"):
                assert affected_branch not in requirement.specifier
        if dependency == "fastmcp":
            assert "4.0.0" not in requirement.specifier
            assert "4.1.1" not in requirement.specifier


@pytest.mark.parametrize("dependency", ["fastmcp", "fastmcp-slim"])
def test_workspace_mcp_constraints_reject_affected_major_branch(dependency: str) -> None:
    """Retain the audited maintenance line across transitive workspace paths."""
    constraints = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["constraint-dependencies"]
    requirement = next(Requirement(value) for value in constraints if Requirement(value).name == dependency)
    assert "3.4.4" not in requirement.specifier
    assert "3.4.10" in requirement.specifier
    assert "4.0.0" not in requirement.specifier
    assert "4.1.1" not in requirement.specifier


@pytest.mark.parametrize(
    ("dependency", "affected", "patched"),
    [("brotli", "1.2.0", "1.2.1"), ("brotlicffi", "1.2.0.1", "1.2.1.0")],
)
def test_workspace_brotli_constraints_cover_every_interpreter(dependency: str, affected: str, patched: str) -> None:
    """Protect both decoder distributions selected by HTTPX's Brotli extra."""
    constraints = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["constraint-dependencies"]
    requirements = [Requirement(value) for value in constraints if Requirement(value).name == dependency]
    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement.marker is None
    assert affected not in requirement.specifier
    assert patched in requirement.specifier
    for implementation in ("CPython", "PyPy"):
        packages = locked_packages(
            {
                "python_version": "3.11",
                "python_full_version": "3.11.0",
                "sys_platform": "linux",
                "platform_machine": "x86_64",
                "platform_python_implementation": implementation,
            }
        )
        assert Version(packages[dependency]) >= Version(patched)


@pytest.mark.parametrize(
    ("manifest", "extra"),
    [("src/bundles/duckduckgo/pyproject.toml", None), ("src/backend/base/pyproject.toml", "duckduckgo")],
)
@pytest.mark.parametrize(
    ("implementation", "dependency", "affected", "patched"),
    [
        ("CPython", "brotli", "1.2.0", "1.2.1"),
        ("PyPy", "brotli", "1.2.0", "1.2.1"),
        ("PyPy", "brotlicffi", "1.2.0.1", "1.2.1.0"),
    ],
)
def test_published_duckduckgo_requirements_protect_the_selected_decoder(
    manifest: str, extra: str | None, implementation: str, dependency: str, affected: str, patched: str
) -> None:
    """Protect both installed decoders because HTTPX always prefers Brotli."""
    project = tomllib.loads((ROOT / manifest).read_text())["project"]
    declarations = project["dependencies"] if extra is None else project["optional-dependencies"][extra]
    requirements = [
        requirement
        for value in declarations
        if (requirement := Requirement(value)).name == dependency
        and (
            requirement.marker is None
            or requirement.marker.evaluate({"platform_python_implementation": implementation})
        )
    ]
    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement.name == dependency
    assert affected not in requirement.specifier
    assert patched in requirement.specifier


@pytest.mark.parametrize("manifest", [MANIFESTS[0], "src/bundles/lfx-bundles/pyproject.toml"])
@pytest.mark.parametrize(
    ("python", "platform", "machine", "supported"),
    [
        ("3.11", "linux", "x86_64", True),
        ("3.11", "win32", "AMD64", True),
        ("3.11", "darwin", "arm64", True),
        ("3.11", "darwin", "x86_64", False),
        ("3.14", "linux", "x86_64", False),
        ("3.14", "darwin", "arm64", False),
    ],
)
def test_cuga_extra_protects_fastmcp_only_where_cuga_is_supported(
    manifest: str, python: str, platform: str, machine: str, *, supported: bool
) -> None:
    """Apply the FastMCP maintenance floor to the CUGA extra's supported platforms."""
    project = tomllib.loads((ROOT / manifest).read_text())["project"]
    environment = {"python_version": python, "sys_platform": platform, "platform_machine": machine}
    requirements = [
        requirement
        for value in project["optional-dependencies"]["cuga"]
        if (requirement := Requirement(value)).name in {"cuga", "fastmcp"}
        and (requirement.marker is None or requirement.marker.evaluate(environment))
    ]
    assert sorted(requirement.name for requirement in requirements) == (["cuga", "fastmcp"] if supported else [])
    if supported:
        requirement = next(requirement for requirement in requirements if requirement.name == "fastmcp")
        assert "3.4.4" not in requirement.specifier
        assert "3.4.10" in requirement.specifier
        assert "4.0.0" not in requirement.specifier
        assert "4.1.1" not in requirement.specifier


@pytest.mark.parametrize("provider", ["git", "cuga", "nvidia", "lmstudio"])
def test_generator_preserves_published_provider_security_requirements(provider: str) -> None:
    """Keep regenerated extras on the same patched ranges as published metadata."""
    generator = runpy.run_path(str(ROOT / "scripts/migrate/consolidate_bundles.py"))
    project = tomllib.loads((ROOT / "src/bundles/lfx-bundles/pyproject.toml").read_text())["project"]
    assert generator["PROVIDER_DEPS"][provider] == project["optional-dependencies"][provider]


@pytest.mark.parametrize("manifest", [MANIFESTS[0], "src/bundles/confluent/pyproject.toml"])
@pytest.mark.parametrize("python", ["3.10", "3.11", "3.14"])
def test_published_pyarrow_requirements_patch_bundled_brotli_on_supported_python(manifest: str, python: str) -> None:
    """Use the patched Arrow maintenance release without breaking Python 3.10."""
    project = tomllib.loads((ROOT / manifest).read_text())["project"]
    declarations = project["optional-dependencies"]["pyarrow"] if manifest == MANIFESTS[0] else project["dependencies"]
    requirements = [
        requirement
        for value in declarations
        if (requirement := Requirement(value)).name == "pyarrow"
        and (requirement.marker is None or requirement.marker.evaluate({"python_version": python}))
    ]
    assert len(requirements) == 1
    requirement = requirements[0]
    if python == "3.10":
        # Arrow's patched 26.x wheels require Python 3.11 or newer.
        assert "23.0.0" not in requirement.specifier
        assert "23.0.1" in requirement.specifier
        assert "24.0.0" not in requirement.specifier
    else:
        assert "26.0.0" not in requirement.specifier
        assert "26.0.1" in requirement.specifier
        assert "27.0.0" not in requirement.specifier


@pytest.mark.parametrize("python", ["3.10", "3.11", "3.14"])
def test_plain_base_requirements_patch_transitive_pyarrow_without_breaking_python310(python: str) -> None:
    """Protect the mandatory Openlayer path in published base wheels."""
    project = tomllib.loads((ROOT / MANIFESTS[0]).read_text())["project"]
    requirements = [
        requirement
        for value in project["dependencies"]
        if (requirement := Requirement(value)).name == "pyarrow"
        and (requirement.marker is None or requirement.marker.evaluate({"python_version": python}))
    ]
    if python == "3.10":
        assert not requirements
    else:
        assert len(requirements) == 1
        assert "26.0.0" not in requirements[0].specifier
        assert "26.0.1" in requirements[0].specifier
        assert "27.0.0" not in requirements[0].specifier


def test_duckduckgo_bundle_requirement_matches_the_current_release_line() -> None:
    """Keep the backport installable without replacing the newer release line's bundle."""
    project = tomllib.loads((ROOT / "src/bundles/duckduckgo/pyproject.toml").read_text())["project"]
    lfx_version = tomllib.loads((ROOT / "src/lfx/pyproject.toml").read_text())["project"]["version"]
    requirement = next(Requirement(value) for value in project["dependencies"] if Requirement(value).name == "lfx")
    assert lfx_version in requirement.specifier
    if Version(lfx_version).release[:2] == (1, 13):
        assert "1.14.0.dev0" not in requirement.specifier
        assert "1.14.0" not in requirement.specifier


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


@pytest.mark.parametrize("python", ["3.10", "3.11", "3.14"])
@pytest.mark.parametrize("regression", ["missing", "lowered"])
def test_pyarrow_extra_rejects_missing_or_lowered_security_floor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, python: str, regression: str
) -> None:
    """Exercise the published-extra check against missing and downgraded metadata."""
    project = tomllib.loads((ROOT / MANIFESTS[0]).read_text())["project"]
    requirements = (
        []
        if regression == "missing"
        else [
            "pyarrow>=23.0.0,<24.0.0; python_version < '3.11'",
            "pyarrow>=26.0.0,<27.0.0; python_version >= '3.11'",
        ]
    )
    manifest = tmp_path / MANIFESTS[0]
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "[project]\ndependencies = "
        + json.dumps(project["dependencies"])
        + "\n[project.optional-dependencies]\npyarrow = "
        + json.dumps(requirements)
        + "\n"
    )
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    with pytest.raises(AssertionError):
        test_published_pyarrow_requirements_patch_bundled_brotli_on_supported_python(MANIFESTS[0], python)


@pytest.mark.parametrize("manifest", ["pyproject.toml", MANIFESTS[0]])
def test_certifi_security_floor_uses_the_restored_patched_trust_store(manifest: str) -> None:
    """Reject affected roots while retaining the unaffected roots restored after the fix."""
    metadata = tomllib.loads((ROOT / manifest).read_text())
    declarations = (
        metadata["tool"]["uv"]["constraint-dependencies"]
        if manifest == "pyproject.toml"
        else metadata["project"]["dependencies"]
    )
    requirements = [Requirement(value) for value in declarations if Requirement(value).name == "certifi"]
    assert len(requirements) == 1
    assert requirements[0].marker is None
    assert "2026.7.22" not in requirements[0].specifier
    assert "2026.10.18" not in requirements[0].specifier
    assert "2026.10.19" in requirements[0].specifier
    assert Version(locked_packages({"python_version": "3.14", "python_full_version": "3.14.0"})["certifi"]) >= Version(
        "2026.10.19"
    )
