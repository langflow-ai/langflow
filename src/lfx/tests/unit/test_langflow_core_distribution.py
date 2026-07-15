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


def test_langflow_core_metadata_contract():
    core = _load_pyproject(CORE_ROOT / "pyproject.toml")
    project = core["project"]
    root_project = _load_pyproject(REPO_ROOT / "pyproject.toml")["project"]
    base_project = _load_pyproject(REPO_ROOT / "src" / "backend" / "base" / "pyproject.toml")["project"]

    assert project["name"] == "langflow-core"
    assert project["version"] == root_project["version"]
    assert project["requires-python"] == root_project["requires-python"]

    base_version = base_project["version"]
    assert project["dependencies"] == [f"langflow-base[complete]~={base_version}"]
    assert project["optional-dependencies"] == {
        "audio": [f"langflow-base[audio]~={base_version}"],
        "postgresql": [f"langflow-base[postgresql]~={base_version}"],
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


def test_langflow_core_is_a_sibling_workspace_distribution():
    root = _load_pyproject(REPO_ROOT / "pyproject.toml")

    assert "src/langflow-core" in root["tool"]["uv"]["workspace"]["members"]
    assert not any(Requirement(requirement).name == "langflow-core" for requirement in root["project"]["dependencies"])
    assert root["project"]["scripts"] == {"langflow": "langflow.langflow_launcher:main"}


def test_langflow_core_wheel_contains_a_nonempty_marker_package():
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
    assert "langflow-base[complete]~=$$LANGFLOW_BASE_VERSION" in makefile
    assert "langflow-base[audio]~=$$LANGFLOW_BASE_VERSION" in makefile
    assert "langflow-base[postgresql]~=$$LANGFLOW_BASE_VERSION" in makefile
