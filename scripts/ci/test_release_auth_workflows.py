"""Release workflow contracts for authentication preparation before publication."""

from pathlib import Path

import pytest
import yaml

from scripts.ci.release_auth.constants import AUTH_SOURCE

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("workflow_name", "job_name", "build_step"),
    [
        ("release.yml", "build-lfx", "Build project for distribution"),
        ("release_nightly.yml", "build-nightly-lfx", "Build LFX for distribution"),
        ("release-lfx.yml", "release-lfx", "Build distribution"),
    ],
)
def test_official_release_builds_prepare_and_verify_wheels(workflow_name: str, job_name: str, build_step: str) -> None:
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows" / workflow_name).read_text())
    step = next(step for step in workflow["jobs"][job_name]["steps"] if step.get("name") == build_step)
    commands = step["run"]

    assert commands.index("release_auth_defaults.py prepare") < commands.index("uv build --wheel")
    assert commands.index("release_auth_defaults.py verify dist/*.whl") > commands.index("uv build --wheel")
    assert not step.get("continue-on-error", False)
    assert "if" not in step


def test_main_release_validates_tagged_source_before_publication() -> None:
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/release.yml").read_text())
    steps = workflow["jobs"]["validate-tag"]["steps"]
    gate = next(step for step in steps if step.get("name") == "Verify tagged source disables auto-login")
    assert "release_auth_defaults.py verify-source" in gate["run"]
    assert gate["if"] == "${{ !inputs.dry_run }}"
    assert not gate.get("continue-on-error", False)


def test_nightly_tag_commit_includes_release_authentication_default() -> None:
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/nightly_build.yml").read_text())
    steps = workflow["jobs"]["create-nightly-tag"]["steps"]
    commands = next(step["run"] for step in steps if step.get("id") == "commit_tag")
    assert commands.index("release_auth_defaults.py prepare") < commands.index("git commit")
    staged = commands[commands.index("git add") : commands.index("git commit")]
    assert AUTH_SOURCE.as_posix() in staged


def test_standalone_lfx_builds_and_github_release_use_the_prepared_commit() -> None:
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/release-lfx.yml").read_text())
    jobs = workflow["jobs"]
    expected = "${{ needs.validate-version.outputs.release_ref }}"
    for name in ["release-lfx", "build-docker", "create-release"]:
        checkout = next(step for step in jobs[name]["steps"] if step.get("uses", "").startswith("actions/checkout@"))
        assert checkout["with"]["ref"] == expected
    release = next(step for step in jobs["create-release"]["steps"] if step.get("name") == "Create Release")
    assert release["with"]["target_commitish"] == expected
