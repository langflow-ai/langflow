"""Contract tests for the bundle-free ``langflow-core`` distribution."""

from __future__ import annotations

from pathlib import Path

from packaging.requirements import Requirement

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[4]
CORE_ROOT = REPO_ROOT / "src" / "langflow-core"


def _load_pyproject(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _minor_compatibility_floor(version: str) -> str:
    major, minor, *_ = version.split(".")
    return f"{major}.{minor}.0"


def test_langflow_core_metadata_contract():
    core = _load_pyproject(CORE_ROOT / "pyproject.toml")
    project = core["project"]
    root_project = _load_pyproject(REPO_ROOT / "pyproject.toml")["project"]
    base_project = _load_pyproject(REPO_ROOT / "src" / "backend" / "base" / "pyproject.toml")["project"]

    assert project["name"] == "langflow-core"
    assert project["version"] == root_project["version"]
    assert project["requires-python"] == root_project["requires-python"]

    base_floor = _minor_compatibility_floor(base_project["version"])
    assert project["dependencies"] == [f"langflow-base[complete]~={base_floor}"]
    assert project["optional-dependencies"] == {
        "audio": [f"langflow-base[audio]~={base_floor}"],
        "postgresql": [f"langflow-base[postgresql]~={base_floor}"],
    }
    assert project["scripts"] == {
        "langflow": "langflow.langflow_launcher:main",
        "langflow-core": "langflow.langflow_launcher:main",
    }


def test_langflow_core_has_no_extension_distribution_dependencies():
    core = _load_pyproject(CORE_ROOT / "pyproject.toml")
    requirements = [
        Requirement(requirement)
        for requirement in [
            *core["project"]["dependencies"],
            *(requirement for extra in core["project"]["optional-dependencies"].values() for requirement in extra),
        ]
    ]

    assert {requirement.name for requirement in requirements} == {"langflow-base"}
    assert not any(requirement.name.startswith("lfx-") for requirement in requirements)


def test_full_langflow_consumes_core_workspace_distribution():
    root = _load_pyproject(REPO_ROOT / "pyproject.toml")
    root_project = root["project"]
    core_project = _load_pyproject(CORE_ROOT / "pyproject.toml")["project"]
    base_project = _load_pyproject(REPO_ROOT / "src" / "backend" / "base" / "pyproject.toml")["project"]
    root_requirements = [Requirement(requirement) for requirement in root_project["dependencies"]]
    root_extra_requirements = [
        Requirement(requirement)
        for extra_requirements in root_project["optional-dependencies"].values()
        for requirement in extra_requirements
    ]
    core_requirements = [Requirement(requirement) for requirement in core_project["dependencies"]]

    assert "src/langflow-core" in root["tool"]["uv"]["workspace"]["members"]
    assert root["tool"]["uv"]["sources"]["langflow-core"] == {"workspace": True}
    core_floor = _minor_compatibility_floor(root_project["version"])
    base_floor = _minor_compatibility_floor(base_project["version"])
    assert f"langflow-core~={core_floor}" in root_project["dependencies"]
    assert root_project["optional-dependencies"]["audio"] == [f"langflow-core[audio]~={core_floor}"]
    assert root_project["optional-dependencies"]["postgresql"] == [f"langflow-core[postgresql]~={core_floor}"]
    assert {requirement.name for requirement in root_requirements}.isdisjoint({"langflow-base", "lfx"})
    assert {requirement.name for requirement in root_extra_requirements}.isdisjoint({"langflow-base", "lfx"})
    assert [requirement.name for requirement in core_requirements] == ["langflow-base"]
    assert str(core_requirements[0].specifier) == f"~={base_floor}"


def test_langflow_core_is_the_only_langflow_console_script_owner():
    distribution_pyprojects = [
        REPO_ROOT / "pyproject.toml",
        CORE_ROOT / "pyproject.toml",
        REPO_ROOT / "src" / "backend" / "base" / "pyproject.toml",
        REPO_ROOT / "src" / "lfx" / "pyproject.toml",
    ]
    langflow_script_owners = [
        pyproject
        for pyproject in distribution_pyprojects
        if "langflow" in _load_pyproject(pyproject)["project"].get("scripts", {})
    ]

    assert langflow_script_owners == [CORE_ROOT / "pyproject.toml"]


def test_langflow_core_source_package_marker_is_nonempty():
    marker = CORE_ROOT / "src" / "langflow_core" / "__init__.py"

    assert marker.read_text(encoding="utf-8").strip()


def test_makefile_exposes_langflow_core_distribution_targets():
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "build_langflow_core:" in makefile
    assert "publish_core:" in makefile
    assert "publish_core_testpypi:" in makefile
    assert "cd src/langflow-core && uv build $(args) --out-dir dist" in makefile
    assert "cd src/langflow-core && uv publish" in makefile


def test_makefile_patch_tracks_langflow_core_version_and_base_dependency():
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "Updating langflow-core pyproject.toml" in makefile
    assert "fname='src/langflow-core/pyproject.toml'" in makefile
    assert "src/langflow-core/pyproject.toml" in makefile
    assert "langflow-core~=$$LANGFLOW_COMPAT_VERSION" in makefile
    assert "langflow-core[audio]~=$$LANGFLOW_COMPAT_VERSION" in makefile
    assert "langflow-core[postgresql]~=$$LANGFLOW_COMPAT_VERSION" in makefile
    assert "langflow-base[complete]~=$$LANGFLOW_BASE_COMPAT_VERSION" in makefile
    assert "langflow-base[audio]~=$$LANGFLOW_BASE_COMPAT_VERSION" in makefile
    assert "langflow-base[postgresql]~=$$LANGFLOW_BASE_COMPAT_VERSION" in makefile
