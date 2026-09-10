from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import tomllib
from packaging.requirements import Requirement

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_release_inventory import resolve_profile, validate_inventory

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "scripts" / "ci" / "release_inventory_contract.json"
RELEASE_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"
GATE_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release-inventory-gate.yml"
OPT_IN_STANDALONE_EXTENSIONS = {
    "lfx-arxiv",
    "lfx-confluent",
    "lfx-duckduckgo",
    "lfx-empiriolabs",
    "lfx-exa",
    "lfx-firecrawl",
    "lfx-nextplaid",
    "lfx-paddle",
    "lfx-valkey",
}


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def workflow_job_block(path: Path, job_name: str) -> str:
    workflow = path.read_text(encoding="utf-8")
    start = workflow.index(f"\n  {job_name}:")
    next_job = re.search(r"\n  [a-z][a-z0-9_-]*:\n", workflow[start + 1 :])
    end = start + 1 + next_job.start() if next_job else len(workflow)
    return workflow[start:end]


def test_contract_tracks_every_long_tail_bundle() -> None:
    expected = resolve_profile(load_contract(), "python-full")["bundle_names"]
    bundles_root = REPO_ROOT / "src" / "bundles" / "lfx-bundles" / "src" / "lfx_bundles"
    actual = sorted(path.name for path in bundles_root.iterdir() if path.is_dir() and (path / "__init__.py").is_file())
    assert expected == actual


def test_contract_tracks_every_curated_extension() -> None:
    expected = resolve_profile(load_contract(), "python-default")["entry_points"]["langflow.extensions"]
    root_project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependency_names = {Requirement(value).name for value in root_project["dependencies"]}

    actual: list[str] = []
    for pyproject_path in sorted((REPO_ROOT / "src" / "bundles").glob("*/pyproject.toml")):
        project = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))["project"]
        if project["name"] in dependency_names:
            actual.extend(project.get("entry-points", {}).get("langflow.extensions", {}))
    assert expected == sorted(actual)


def test_bundles_extra_owns_the_opt_in_standalone_extensions() -> None:
    contract = load_contract()
    root_project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    default_dependencies = {Requirement(value).name for value in root_project["dependencies"]}
    bundle_dependencies = {Requirement(value).name for value in root_project["optional-dependencies"]["bundles"]}
    default_profile = resolve_profile(contract, "python-default")
    full_profile = resolve_profile(contract, "python-full")

    assert default_dependencies.isdisjoint(OPT_IN_STANDALONE_EXTENSIONS)
    assert bundle_dependencies >= OPT_IN_STANDALONE_EXTENSIONS
    assert set(default_profile["forbidden_distributions"]) >= OPT_IN_STANDALONE_EXTENSIONS
    assert set(full_profile["required_distributions"]) >= OPT_IN_STANDALONE_EXTENSIONS
    assert OPT_IN_STANDALONE_EXTENSIONS.isdisjoint(full_profile["forbidden_distributions"])
    assert OPT_IN_STANDALONE_EXTENSIONS.isdisjoint(default_profile["entry_points"]["langflow.extensions"])
    assert set(full_profile["entry_points"]["langflow.extensions"]) >= OPT_IN_STANDALONE_EXTENSIONS


def test_contract_required_files_exist_in_sources() -> None:
    source_roots = {
        "langflow-base": REPO_ROOT / "src" / "backend" / "base",
        "lfx-azure": REPO_ROOT / "src" / "bundles" / "azure" / "src",
        "lfx-datastax": REPO_ROOT / "src" / "bundles" / "datastax" / "src",
        "lfx-google": REPO_ROOT / "src" / "bundles" / "google" / "src",
        "lfx-ollama": REPO_ROOT / "src" / "bundles" / "ollama" / "src",
        "lfx-openai": REPO_ROOT / "src" / "bundles" / "openai" / "src",
        "lfx-toolguard": REPO_ROOT / "src" / "bundles" / "toolguard" / "src",
        "lfx-bundles": REPO_ROOT / "src" / "bundles" / "lfx-bundles" / "src",
    }

    for profile_name in ("python-base", "python-default", "python-full"):
        required_files = resolve_profile(load_contract(), profile_name)["required_files"]
        for distribution, patterns in required_files.items():
            for pattern in patterns:
                assert list(source_roots[distribution].glob(pattern)), f"{profile_name}: {distribution}/{pattern}"


def test_base_profiles_forbid_extensions_and_torch() -> None:
    for profile_name in ("python-base", "image-base"):
        profile = resolve_profile(load_contract(), profile_name)
        assert profile["forbidden_distribution_prefixes"] == ["lfx-"]
        assert {"langflow", "lfx-bundles", "torch", "torchvision"} <= set(profile["forbidden_distributions"])
        assert {"langflow-base", "lfx", "langflow-sdk"} <= set(profile["required_distributions"])


def test_default_and_full_profiles_are_no_torch() -> None:
    for profile_name in ("python-default", "python-full", "image-default", "image-full"):
        profile = resolve_profile(load_contract(), profile_name)
        assert {"torch", "torchvision"} <= set(profile["forbidden_distributions"])
    assert "lfx-bundles" not in resolve_profile(load_contract(), "python-default")["required_distributions"]
    assert "lfx-bundles" in resolve_profile(load_contract(), "python-full")["required_distributions"]


def test_full_python_profile_uses_the_reviewed_root_extra() -> None:
    root_project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    bundle_dependencies = {Requirement(value).name for value in root_project["optional-dependencies"]["bundles"]}
    assert bundle_dependencies == {"lfx-bundles", *OPT_IN_STANDALONE_EXTENSIONS}
    gate = GATE_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert 'MAIN_TARGET="langflow[bundles] @ file://${PWD}/${MAIN_WHEELS[0]}"' in gate


def test_validation_reports_missing_forbidden_and_component_drift() -> None:
    profile = {
        "required_distributions": ["langflow", "lfx"],
        "forbidden_distributions": ["lfx-bundles"],
        "exact_distributions": True,
        "entry_points": {"langflow.extensions": ["lfx-openai"]},
        "bundle_names": [],
        "required_files": {"langflow": ["langflow/required.py"]},
    }
    actual = {
        "managed_distributions": {"langflow": "1.0", "lfx-bundles": "1.0"},
        "entry_points": {"langflow.extensions": []},
        "bundle_names": ["unexpected"],
    }

    errors, file_matches = validate_inventory(profile, actual, {"langflow": []}, [])

    assert any("missing required distributions" in error and "lfx" in error for error in errors)
    assert any("unexpected managed distributions" in error and "lfx-bundles" in error for error in errors)
    assert any("forbidden distributions installed" in error and "lfx-bundles" in error for error in errors)
    assert any("entry-point group" in error for error in errors)
    assert any("bundle inventory" in error for error in errors)
    assert file_matches == {"langflow": {"langflow/required.py": False}}


def test_release_gate_covers_supported_python_and_image_architectures() -> None:
    profile_job = workflow_job_block(GATE_WORKFLOW_PATH, "downstream-bundle-profiles")
    base_job = workflow_job_block(GATE_WORKFLOW_PATH, "python-base-inventory")
    python_job = workflow_job_block(GATE_WORKFLOW_PATH, "python-inventory")
    image_job = workflow_job_block(GATE_WORKFLOW_PATH, "image-inventory")

    assert "manage_bundle_profiles.py check" in profile_job
    assert "manage_bundle_profiles.py compile" in profile_job
    assert "if: ${{ inputs.base-artifact-name != '' }}" in base_job
    assert 'python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]' in base_job
    assert "--profile python-base" in base_job
    for wheel_dir in ("sdk-dist", "lfx-dist", "base-dist"):
        assert wheel_dir in base_job
    assert "main-dist" not in base_job
    assert "bundles-dist" not in base_job
    assert "profile: [python-default, python-full]" in python_job
    assert image_job.count("- arch: amd64") == 1
    assert image_job.count("- arch: arm64") == 1
    assert "--target base" in image_job
    assert "--target full" in image_job
    assert "--target full-bundles" in image_job

    # Runtime images use a non-root UID that differs from the runner. Only the
    # exact report files should be writable through the bind mount.
    assert ': > "$report"' in image_job
    assert 'chmod a+rw "$report"' in image_job
    assert "chmod -R" not in image_job


def test_release_publication_and_images_depend_on_inventory_gate() -> None:
    for job_name in ("publish-base", "publish-bundles", "publish-main", "publish-sdk", "publish-lfx"):
        job = workflow_job_block(RELEASE_WORKFLOW_PATH, job_name)
        assert "release-inventory" in job
        assert "needs.release-inventory.result" in job

    for job_name in ("call_docker_build_base", "call_docker_build_main", "call_docker_build_main_all"):
        job = workflow_job_block(RELEASE_WORKFLOW_PATH, job_name)
        assert "release-inventory" in job
        assert "needs.release-inventory.result == 'success'" in job


def test_release_inventory_gate_receives_base_and_full_artifacts() -> None:
    gate = workflow_job_block(RELEASE_WORKFLOW_PATH, "release-inventory")

    assert "needs.build-base.result == 'success'" in gate
    assert "needs.build-main.result == 'success'" in gate
    assert "inputs.build_docker_base" in gate
    assert "inputs.build_docker_main" in gate
    assert "base-artifact-name: ${{ needs.build-base.result == 'success' && 'dist-base' || '' }}" in gate
    assert "main-artifact-name: ${{ needs.build-main.result == 'success' && 'dist-main' || '' }}" in gate
    assert "core-artifact-name" not in gate
