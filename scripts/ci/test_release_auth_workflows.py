"""Release workflow contracts for authentication preparation before publication."""

import json
import shutil
import subprocess
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
        ("cross-platform-test.yml", "build-if-needed", "Build LFX package"),
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


def test_base_startup_installs_release_lfx_after_workspace_dependencies() -> None:
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/release.yml").read_text())
    commands = next(step["run"] for step in workflow["jobs"]["build-base"]["steps"] if step.get("name") == "Test CLI")
    assert (
        commands.index("uv pip install src/backend/base/dist/*.whl")
        < commands.index("uv pip install --force-reinstall --no-deps lfx-dist/*.whl")
        < commands.index("uv run --no-sync python -m langflow run")
    )


def test_candidate_updates_and_release_publication_share_a_non_cancelling_lock() -> None:
    inputs = {
        "prepare-release-tag.yml": ("tag", "v1.13.0"),
        "release.yml": ("release_tag", "v1.13.0"),
        "create-release.yml": ("version", "1.13.0"),
    }
    groups = set()
    for filename, (input_name, value) in inputs.items():
        workflow = yaml.safe_load((REPO_ROOT / ".github/workflows" / filename).read_text())
        lock = workflow["concurrency"]
        groups.add(lock["group"].replace("${{ inputs." + input_name + " }}", value))
        assert lock["cancel-in-progress"] is False
    assert len(groups) == 1
    assert "${{" not in next(iter(groups))


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"prerelease": True}, "allowed"),
        ({"prerelease": False}, "refused"),
        ({"status": 404}, "allowed"),
        ({"status": 403}, "refused"),
        ({"status": 500}, "refused"),
    ],
)
def test_candidate_workflow_protects_final_releases_and_fails_closed(response: dict, expected: str) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the GitHub Actions publication guard")
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/prepare-release-tag.yml").read_text())
    steps = workflow["jobs"]["prepare-tag"]["steps"]
    guard = next(step for step in steps if step.get("name") == "Protect published final releases")
    assert guard["if"] == "inputs.replace_prepared_tag"
    assert not guard.get("continue-on-error", False)
    # Execute the workflow's JavaScript with an in-memory GitHub API response.
    script = f"""
      const response = {json.dumps(response)};
      let refused = false;
      const core = {{setFailed: () => {{refused = true;}}}};
      const context = {{repo: {{owner: 'test', repo: 'test'}}}};
      const github = {{rest: {{repos: {{getReleaseByTag: async () => {{
        if (response.status) throw response;
        return {{data: response}};
      }}}}}}}};
      try {{
        {guard["with"]["script"]}
      }} catch {{ refused = true; }}
      console.log(refused ? 'refused' : 'allowed');
    """
    # Only the checked-in workflow and fixed test responses are executed.
    result = subprocess.run(  # noqa: S603
        [node, "--input-type=module"], input=script, text=True, capture_output=True, check=True
    )
    assert result.stdout.strip() == expected
    push_step = next(step for step in steps if step.get("name") == "Create and push the release source tag")
    assert steps.index(guard) < steps.index(push_step)
    push = push_step["run"]
    assert '--replace-prepared-tag "$expected"' in push
    assert '--force-with-lease="$tag_ref:$expected"' in push
