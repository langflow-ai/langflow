"""Keep package requirements and release Python coverage aligned."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import tomllib
import yaml
from packaging.specifiers import SpecifierSet

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SUPPORTED = {"3.11", "3.12", "3.13", "3.14"}
EXPERIMENTAL = "3.15"


def workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


@pytest.mark.parametrize("member", [".", "src/backend/base", "src/lfx", "src/sdk", "src/langflow-stepflow"])
def test_core_packages_share_the_supported_python_range(member: str) -> None:
    project = tomllib.loads((REPO_ROOT / member / "pyproject.toml").read_text())["project"]
    versions = SpecifierSet(project["requires-python"])
    assert versions == SpecifierSet(">=3.11,<3.16")


@pytest.mark.parametrize("name", ["ci.yml", "python_test.yml", "backend-unit-tests.yml", "store_pytest_durations.yml"])
def test_default_ci_includes_floor_stable_and_experimental_python(name: str) -> None:
    for event in workflow(name)[True].values():
        if not isinstance(event, dict):
            continue
        inputs = event.get("inputs", {})
        if "python-versions" in inputs:
            versions = set(ast.literal_eval(inputs["python-versions"]["default"]))
            assert {"3.11", "3.14", EXPERIMENTAL} <= versions
            assert "3.10" not in versions


@pytest.mark.parametrize(("name", "job"), [("release.yml", "ci"), ("nightly_build.yml", "backend-unit-tests")])
def test_release_and_nightly_request_every_python_version(name: str, job: str) -> None:
    versions = ast.literal_eval(workflow(name)["jobs"][job]["with"]["python-versions"])
    assert set(versions) == SUPPORTED | {EXPERIMENTAL}


def test_installation_gate_requires_stable_versions_and_allows_only_315_to_fail() -> None:
    jobs = workflow("cross-platform-test.yml")["jobs"]
    stable = jobs["test-installation-stable"]
    preview = jobs["test-installation-experimental"]
    assert not stable.get("continue-on-error", False)
    assert preview["continue-on-error"] is True
    for os_name in ("linux", "macos", "windows"):
        assert {
            leg["python-version"] for leg in stable["strategy"]["matrix"]["include"] if leg["os"] == os_name
        } == SUPPORTED
    assert {leg["python-version"] for leg in preview["strategy"]["matrix"]["include"]} == {EXPERIMENTAL}
    for name in ("release.yml", "release_nightly.yml"):
        assert workflow(name)["jobs"]["test-cross-platform"]["uses"] == "./.github/workflows/cross-platform-test.yml"


@pytest.mark.parametrize("job_name", ["test", "report"])
def test_backend_preview_does_not_block_required_versions(job_name: str) -> None:
    job = workflow("backend-unit-tests.yml")["jobs"][job_name]
    assert job["continue-on-error"] == "${{ matrix.python-version == '3.15' }}"
    assert job["strategy"]["fail-fast"] is False


def test_backend_coverage_follows_the_supported_floor() -> None:
    text = (WORKFLOWS / "backend-unit-tests.yml").read_text()
    assert "if [ \"$PYTHON_VERSION\" == '3.11' ]; then" in text
    job = workflow("backend-unit-tests.yml")["jobs"]["test"]
    upload = next(step for step in job["steps"] if step.get("name") == "Upload coverage to Codecov")
    assert upload["if"] == "inputs.publish-coverage && matrix.python-version == '3.11'"


@pytest.mark.parametrize(
    "name",
    [
        "python_test.yml",
        "release-lfx.yml",
        "release-inventory-gate.yml",
        "sqlite-runtime.yml",
        "release_bundles.yml",
        "integration_tests.yml",
    ],
)
def test_experimental_matrix_failures_cannot_cancel_stable_versions(name: str) -> None:
    for job in workflow(name)["jobs"].values():
        if "strategy" in job and "3.15" in str(job["strategy"]["matrix"]):
            assert job["continue-on-error"] in {
                "${{ matrix.python-version == '3.15' }}",
                "${{ matrix.python == '3.15' }}",
            }
            assert job["strategy"]["fail-fast"] is False
