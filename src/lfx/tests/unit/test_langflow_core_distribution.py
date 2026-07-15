"""Contract tests for the bundle-free ``langflow-core`` distribution."""

from __future__ import annotations

from pathlib import Path

import tomllib
from packaging.requirements import Requirement

REPO_ROOT = Path(__file__).resolve().parents[4]
CORE_ROOT = REPO_ROOT / "src" / "langflow-core"


def _load_pyproject(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_langflow_core_metadata_contract():
    core = _load_pyproject(CORE_ROOT / "pyproject.toml")
    project = core["project"]

    assert project["name"] == "langflow-core"
    assert project["version"] == "1.11.0"
    assert project["requires-python"] == ">=3.10,<3.15"
    assert project["dependencies"] == ["langflow-base[complete]~=0.11.0"]
    assert project["optional-dependencies"] == {"postgresql": ["langflow-base[postgresql]~=0.11.0"]}
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
            *core["project"]["optional-dependencies"]["postgresql"],
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
    assert "cd src/langflow-core && uv build $(args)" in makefile
    assert "cd src/langflow-core && uv publish" in makefile


def test_makefile_patch_tracks_langflow_core_version_and_base_dependency():
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "Updating langflow-core pyproject.toml" in makefile
    assert "fname='src/langflow-core/pyproject.toml'" in makefile
    assert "src/langflow-core/pyproject.toml" in makefile
    assert "langflow-base[complete]~=$$LANGFLOW_BASE_VERSION" in makefile
    assert "langflow-base[postgresql]~=$$LANGFLOW_BASE_VERSION" in makefile
