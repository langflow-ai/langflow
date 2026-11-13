"""Regression tests for security dependency floors in published package metadata."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest
from packaging.markers import Marker
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
    """Keep workspace overrides above their patched dependency floors."""
    overrides = _load_pyproject("pyproject.toml")["tool"]["uv"]["override-dependencies"]

    gitpython = _requirement(overrides, "GitPython")
    _assert_floor(gitpython, "3.2.1")

    pypdf = _requirement(overrides, "pypdf")
    _assert_floor(pypdf, "6.19.0")
    _assert_specifier(pypdf, "<", "7.0.0")

    h2 = _requirement(overrides, "h2")
    _assert_floor(h2, "4.4.1")


def test_workspace_security_constraints_enforce_patched_versions() -> None:
    uv_settings = _load_pyproject("pyproject.toml")["tool"]["uv"]
    constraints = uv_settings["constraint-dependencies"]

    _assert_floor(_requirement(constraints, "fsspec"), "2026.6.0")
    _assert_floor(_requirement(constraints, "multidict"), "6.9.1")
    _assert_floor(_requirement(constraints, "langgraph"), "1.2.14")
    _assert_floor(_requirement(constraints, "langgraph-sdk"), "0.4.6")

    # An override replaces every requirement on the package, dropping caps such as
    # aiohttp's multidict<7.0, langgraph's langgraph-sdk<0.5.0, and Opik's LiteLLM cap. Keep these floors
    # as constraints so `uv pip compile` (the Mend export) cannot resolve past them.
    override_names = {Requirement(spec).name.lower() for spec in uv_settings["override-dependencies"]}
    assert not {"multidict", "langgraph-sdk", "litellm"} & override_names


def test_managed_dependency_graph_excludes_opendsstar_and_diskcache() -> None:
    """Even opt-in extras and test groups must not reintroduce the retired dependency."""
    with (REPO_ROOT / "uv.lock").open("rb") as lock_file:
        packages = tomllib.load(lock_file)["package"]
    package_names = {package["name"] for package in packages}
    assert not {"opendsstar", "diskcache"} & package_names

    generator = runpy.run_path(str(REPO_ROOT / "scripts/migrate/consolidate_bundles.py"))
    requirements = {Requirement(spec).name.lower() for specs in generator["PROVIDER_DEPS"].values() for spec in specs}
    assert not {"opendsstar", "diskcache"} & requirements


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
        _assert_floor(pypdf, "6.19.0")
        _assert_specifier(pypdf, "<", "7.0.0")

    base_extras = _load_pyproject("src/backend/base/pyproject.toml")["project"]["optional-dependencies"]
    pypdf_extra = _requirement(base_extras["pypdf"], "pypdf")
    _assert_floor(pypdf_extra, "6.19.0")
    _assert_specifier(pypdf_extra, "<", "7.0.0")


def test_published_packages_enforce_patched_mcp_floor() -> None:
    for relative_path in ("src/backend/base/pyproject.toml", "src/lfx/pyproject.toml"):
        dependencies = _load_pyproject(relative_path)["project"]["dependencies"]
        mcp = _requirement(dependencies, "mcp")
        _assert_floor(mcp, "1.30.0")
        _assert_specifier(mcp, "<", "2.0.0")

    base_extras = _load_pyproject("src/backend/base/pyproject.toml")["project"]["optional-dependencies"]
    _assert_floor(_requirement(base_extras["mcp"], "mcp"), "1.30.0")


def test_published_extras_enforce_patched_gitpython_floor() -> None:
    """Preserve the GitPython fix in both published extras and their generator."""
    base_extras = _load_pyproject("src/backend/base/pyproject.toml")["project"]["optional-dependencies"]
    _assert_floor(_requirement(base_extras["gitpython"], "GitPython"), "3.2.1")

    bundle_extras = _load_pyproject("src/bundles/lfx-bundles/pyproject.toml")["project"]["optional-dependencies"]
    _assert_floor(_requirement(bundle_extras["git"], "GitPython"), "3.2.1")

    generator = runpy.run_path(str(REPO_ROOT / "scripts/migrate/consolidate_bundles.py"))
    assert generator["PROVIDER_DEPS"]["git"] == bundle_extras["git"]


def test_workspace_constraints_enforce_patched_pymongo() -> None:
    constraints = _load_pyproject("pyproject.toml")["tool"]["uv"]["constraint-dependencies"]

    pymongo = _requirement(constraints, "pymongo")
    _assert_floor(pymongo, "4.18.3")
    _assert_specifier(pymongo, "<", "5.0.0")

    with (REPO_ROOT / "uv.lock").open("rb") as lock_file:
        packages = tomllib.load(lock_file)["package"]
    versions = [Version(package["version"]) for package in packages if package["name"] == "pymongo"]
    assert versions
    assert min(versions) >= Version("4.18.3")


@pytest.mark.parametrize(("python_version", "minimum"), [("3.10", "6.5.10"), ("3.11", "6.6"), ("3.14", "6.6")])
def test_tornado_floor_and_lock_match_supported_python(python_version: str, minimum: str) -> None:
    env = {"python_version": python_version, "python_full_version": python_version + ".0"}
    constraints = _load_pyproject("pyproject.toml")["tool"]["uv"]["constraint-dependencies"]
    applicable = [
        req
        for req in map(Requirement, constraints)
        if req.name == "tornado" and (not req.marker or req.marker.evaluate(env))
    ]
    assert len(applicable) == 1
    _assert_floor(applicable[0], minimum)

    with (REPO_ROOT / "uv.lock").open("rb") as lock_file:
        packages = tomllib.load(lock_file)["package"]
    versions = [
        Version(pkg["version"])
        for pkg in packages
        if pkg["name"] == "tornado"
        and (not pkg.get("resolution-markers") or any(Marker(m).evaluate(env) for m in pkg["resolution-markers"]))
    ]
    assert len(versions) == 1
    assert versions[0] >= Version(minimum)


def test_published_packages_enforce_patched_pymongo_floor() -> None:
    """langchain-mongodb is a core langflow-base dependency, so pymongo is always installed.

    The floor must be published on that unconditional path, not only on the mongodb extras.
    """
    base_project = _load_pyproject("src/backend/base/pyproject.toml")["project"]
    bundle_extras = _load_pyproject("src/bundles/lfx-bundles/pyproject.toml")["project"]["optional-dependencies"]
    for requirements in (
        base_project["dependencies"],
        base_project["optional-dependencies"]["mongodb"],
        bundle_extras["mongodb"],
    ):
        pymongo = _requirement(requirements, "pymongo")
        _assert_floor(pymongo, "4.18.3")
        _assert_specifier(pymongo, "<", "5.0.0")

    generator = runpy.run_path(str(REPO_ROOT / "scripts/migrate/consolidate_bundles.py"))
    assert generator["PROVIDER_DEPS"]["mongodb"] == bundle_extras["mongodb"]


def test_first_community_migration_has_no_direct_dependency_edges() -> None:
    generator = runpy.run_path(str(REPO_ROOT / "scripts/migrate/consolidate_bundles.py"))
    extras = _load_pyproject("src/bundles/lfx-bundles/pyproject.toml")["project"]["optional-dependencies"]
    for name in ("apify", "chroma", "cloudflare", "needle"):
        assert extras[name] == generator["PROVIDER_DEPS"][name]
        assert "langchain-community" not in {Requirement(spec).name for spec in extras[name]}
    for name in ("ibm", "oracle"):
        deps = _load_pyproject(f"src/bundles/{name}/pyproject.toml")["project"]["dependencies"]
        assert "langchain-community" not in {Requirement(spec).name for spec in deps}
    oracle = _load_pyproject("src/bundles/oracle/pyproject.toml")["project"]["dependencies"]
    _assert_floor(_requirement(oracle, "langchain-oracledb"), "1.5.0")


def test_provider_upgrades_remove_indirect_community_requirements() -> None:
    with (REPO_ROOT / "uv.lock").open("rb") as lock_file:
        packages = tomllib.load(lock_file)["package"]
    for name, minimum in (("langchain-cohere", "0.6.0"), ("langchain-google-community", "5.0.0")):
        matches = [package for package in packages if package["name"] == name]
        assert matches
        for package in matches:
            assert Version(package["version"]) >= Version(minimum)
            assert "langchain-community" not in {dep["name"] for dep in package.get("dependencies", [])}


def test_workspace_security_overrides_enforce_current_python_floors() -> None:
    """Preserve current Python security floors and the LiteLLM maintenance cap."""
    project = _load_pyproject("pyproject.toml")
    constraints = project["tool"]["uv"]["constraint-dependencies"]
    overrides = project["tool"]["uv"]["override-dependencies"]

    oauthlib = _requirement(constraints, "oauthlib")
    _assert_floor(oauthlib, "4.0.1")
    _assert_specifier(oauthlib, "<", "5.0.0")

    pyjwt = _requirement(overrides, "PyJWT")
    _assert_floor(pyjwt, "2.15.1")
    _assert_specifier(pyjwt, "<", "3.0.0")

    urllib3 = _requirement(overrides, "urllib3")
    _assert_floor(urllib3, "2.8.0")
    _assert_specifier(urllib3, "<", "3.0.0")

    for name, minimum in (("authlib", "1.8.0"), ("virtualenv", "21.14.2"), ("Werkzeug", "3.1.9")):
        _assert_floor(_requirement(overrides, name), minimum)

    litellm = _requirement(constraints, "litellm")
    _assert_floor(litellm, "1.103.10")
    _assert_specifier(litellm, "!=", "1.104.0rc1")
    _assert_specifier(litellm, "!=", "1.107.0")
    _assert_specifier(litellm, "<", "1.104.0")

    with (REPO_ROOT / "uv.lock").open("rb") as lock_file:
        packages = tomllib.load(lock_file)["package"]
    for name, minimum in (
        ("oauthlib", "4.0.1"),
        ("pyjwt", "2.15.1"),
        ("urllib3", "2.8.0"),
        ("litellm", "1.103.10"),
        ("a2a-sdk", "1.2.1"),
        ("authlib", "1.8.0"),
        ("virtualenv", "21.14.2"),
        ("werkzeug", "3.1.9"),
    ):
        matches = [package for package in packages if package["name"] == name]
        assert matches
        for package in matches:
            assert Version(package["version"]) >= Version(minimum)


def test_published_packages_enforce_current_python_floors() -> None:
    """Publish the security floors required by installs outside this workspace."""
    root_dependencies = _load_pyproject("pyproject.toml")["project"]["dependencies"]
    base_project = _load_pyproject("src/backend/base/pyproject.toml")["project"]
    lfx_dependencies = _load_pyproject("src/lfx/pyproject.toml")["project"]["dependencies"]
    google_dependencies = _load_pyproject("src/bundles/google/pyproject.toml")["project"]["dependencies"]

    oauthlib = _requirement(root_dependencies, "oauthlib")
    _assert_floor(oauthlib, "4.0.1")
    _assert_specifier(oauthlib, "<", "5.0.0")

    google_oauthlib = _requirement(google_dependencies, "oauthlib")
    _assert_floor(google_oauthlib, "4.0.1")
    _assert_specifier(google_oauthlib, "<", "5.0.0")

    for requirements in (base_project["dependencies"], lfx_dependencies):
        pyjwt = _requirement(requirements, "PyJWT")
        _assert_floor(pyjwt, "2.15.1")
        _assert_specifier(pyjwt, "<", "3.0.0")

    a2a_sdk = _requirement(base_project["dependencies"], "a2a-sdk")
    _assert_floor(a2a_sdk, "1.2.1")
    _assert_specifier(a2a_sdk, "<", "2.0.0")

    urllib3 = _requirement(base_project["dependencies"], "urllib3")
    _assert_floor(urllib3, "2.8.0")
    _assert_specifier(urllib3, "<", "3.0.0")

    litellm = _requirement(base_project["optional-dependencies"]["litellm"], "litellm")
    _assert_floor(litellm, "1.103.10")
    _assert_specifier(litellm, "!=", "1.104.0rc1")
    _assert_specifier(litellm, "!=", "1.107.0")
    _assert_specifier(litellm, "<", "1.104.0")

    bundle_extras = _load_pyproject("src/bundles/lfx-bundles/pyproject.toml")["project"]["optional-dependencies"]
    for cuga_requirements in (base_project["optional-dependencies"]["cuga"], bundle_extras["cuga"]):
        cuga_litellm = [Requirement(spec) for spec in cuga_requirements if Requirement(spec).name.lower() == "litellm"]
        assert len(cuga_litellm) == 2
        for requirement in cuga_litellm:
            _assert_floor(requirement, "1.103.10")
            _assert_specifier(requirement, "!=", "1.104.0rc1")
            _assert_specifier(requirement, "!=", "1.107.0")
            _assert_specifier(requirement, "<", "1.104.0")

    generator = runpy.run_path(str(REPO_ROOT / "scripts/migrate/consolidate_bundles.py"))
    assert generator["PROVIDER_DEPS"]["cuga"] == bundle_extras["cuga"]


def test_standalone_lfx_bundles_extra_requires_patched_legacy_metadata() -> None:
    """Standalone bundle installs must retain the published PyMongo security floor."""
    extras = _load_pyproject("src/lfx/pyproject.toml")["project"]["optional-dependencies"]
    legacy_bundle = _requirement(extras["bundles"], "lfx-bundles")
    assert "1.1.40" not in legacy_bundle.specifier
    assert "1.1.41" in legacy_bundle.specifier
