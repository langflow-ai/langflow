"""Contract tests for the runnable, bundle-free ``langflow-base`` distribution."""

from __future__ import annotations

from pathlib import Path

from packaging.requirements import Requirement

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[4]
BASE_ROOT = REPO_ROOT / "src" / "backend" / "base"


def _load_pyproject(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _minor_compatibility_floor(version: str) -> str:
    major, minor, *_ = version.split(".")
    return f"{major}.{minor}.0"


def test_langflow_base_metadata_contract():
    project = _load_pyproject(BASE_ROOT / "pyproject.toml")["project"]
    root_project = _load_pyproject(REPO_ROOT / "pyproject.toml")["project"]

    assert project["name"] == "langflow-base"
    assert project["version"] == root_project["version"]
    assert project["requires-python"] == root_project["requires-python"]
    assert project["optional-dependencies"]["complete"] == []
    assert project["optional-dependencies"]["all"] == []
    assert project["scripts"] == {"langflow": "langflow.langflow_launcher:main"}


def test_langflow_base_default_is_service_complete_without_extensions_or_torch():
    project = _load_pyproject(BASE_ROOT / "pyproject.toml")["project"]
    requirements = [Requirement(requirement) for requirement in project["dependencies"]]
    requirement_names = {requirement.name for requirement in requirements}

    assert {
        "redis",
        "chromadb",
        "mcp",
        "kubernetes",
        "aiobotocore",
        "langfuse",
        "langwatch",
        "langsmith",
        "arize-phoenix-otel",
        "openinference-instrumentation-langchain",
        "opik",
        "traceloop-sdk",
        "openlayer",
    } <= requirement_names
    assert not any(name.startswith("lfx-") for name in requirement_names)
    assert requirement_names.isdisjoint({"torch", "torchvision", "litellm"})


def test_full_langflow_consumes_base_workspace_distribution():
    root = _load_pyproject(REPO_ROOT / "pyproject.toml")
    root_project = root["project"]
    root_requirements = [Requirement(requirement) for requirement in root_project["dependencies"]]

    assert "src/backend/base" in root["tool"]["uv"]["workspace"]["members"]
    assert "src/langflow-core" not in root["tool"]["uv"]["workspace"]["members"]
    assert root["tool"]["uv"]["sources"]["langflow-base"] == {"workspace": True}
    assert "langflow-core" not in root["tool"]["uv"]["sources"]
    base_floor = _minor_compatibility_floor(root_project["version"])
    assert f"langflow-base~={base_floor}" in root_project["dependencies"]
    assert root_project["optional-dependencies"]["audio"] == [f"langflow-base[audio]~={base_floor}"]
    assert root_project["optional-dependencies"]["postgresql"] == [f"langflow-base[postgresql]~={base_floor}"]
    assert "langflow-base" in {requirement.name for requirement in root_requirements}
    assert any(requirement.name.startswith("lfx-") for requirement in root_requirements)


def test_langflow_base_is_the_only_langflow_console_script_owner():
    root = _load_pyproject(REPO_ROOT / "pyproject.toml")
    workspace_members = root["tool"]["uv"]["workspace"]["members"]
    distribution_pyprojects = sorted({REPO_ROOT / member / "pyproject.toml" for member in workspace_members})
    langflow_script_owners = [
        pyproject
        for pyproject in distribution_pyprojects
        if "langflow" in _load_pyproject(pyproject)["project"].get("scripts", {})
    ]

    assert langflow_script_owners == [BASE_ROOT / "pyproject.toml"]


def test_langflow_core_distribution_is_retired():
    assert not (REPO_ROOT / "src" / "langflow-core" / "pyproject.toml").exists()


def test_makefile_exposes_only_base_and_full_distribution_targets():
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "build_langflow_base:" in makefile
    assert "publish_base:" in makefile
    assert "build_langflow_core:" not in makefile
    assert "publish_core:" not in makefile


def test_makefile_patch_keeps_full_base_and_lfx_versions_aligned():
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "Updating langflow-base pyproject.toml" in makefile
    assert "fname='src/backend/base/pyproject.toml'" in makefile
    assert "langflow-base~=$$LANGFLOW_COMPAT_VERSION" in makefile
    assert "langflow-base[audio]~=$$LANGFLOW_COMPAT_VERSION" in makefile
    assert "langflow-base[postgresql]~=$$LANGFLOW_COMPAT_VERSION" in makefile
    assert "LFX (synced): $$LANGFLOW_VERSION" in makefile
    assert "langflow-core" not in makefile
