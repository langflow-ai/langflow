"""Offline coverage for coordinated OSS release-branch creation."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

import scripts.ci.coordinated_release.branches as branch_cli
from scripts.ci.coordinated_release.branches import (
    BranchAutomationError,
    BranchDiscrepancy,
    GitHubAPIError,
    command_verifier,
    ensure_branch,
    plan_branches,
    process_event,
    validate_merge_event,
)

REPOSITORY = "langflow-ai/langflow"
HEAD = "a" * 40
MERGE = "b" * 40
DESCENDANT = "c" * 40
OTHER = "d" * 40


def pull_request(*, source: str = "release-1.14.0", merged: bool = True, head_sha: str = HEAD) -> dict[str, Any]:
    return {
        "id": 91,
        "number": 17,
        "merged": merged,
        "merge_commit_sha": MERGE,
        "base": {"ref": "main", "sha": MERGE, "repo": {"full_name": REPOSITORY}},
        "head": {"ref": source, "sha": head_sha, "repo": {"full_name": REPOSITORY}},
    }


def event(pr: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "action": "closed",
        "repository": {"full_name": REPOSITORY},
        "pull_request": copy.deepcopy(pr or pull_request()),
    }


class FakeClient:
    def __init__(self, pr: dict[str, Any], *, branches: dict[str, str] | None = None, race: set[str] | None = None):
        self.pr = copy.deepcopy(pr)
        self.branches = dict(branches or {})
        self.race = set(race or ())
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.gets: list[str] = []

    def get(self, path: str) -> dict[str, Any]:
        self.gets.append(path)
        if path.endswith("/pulls/17"):
            return copy.deepcopy(self.pr)
        prefix = f"/repos/{REPOSITORY}/git/ref/heads/"
        if path.startswith(prefix):
            branch = path.removeprefix(prefix)
            if branch not in self.branches:
                raise GitHubAPIError(404, "not found")
            return {"object": {"sha": self.branches[branch]}}
        if "/compare/" in path:
            source, branch = path.rsplit("/compare/", 1)[1].split("...", 1)
            branch = branch.replace("%2E", ".")
            current = self.branches[branch]
            status = "ahead" if current == DESCENDANT else "diverged"
            base_sha = source if status == "ahead" else OTHER
            return {
                "status": status,
                "base_commit": {"sha": base_sha},
                "merge_base_commit": {"sha": base_sha},
                "head_commit": {"sha": current},
            }
        msg = f"unexpected GET {path}"
        raise AssertionError(msg)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.posts.append((path, payload))
        branch = payload["ref"].removeprefix("refs/heads/")
        if branch in self.race:
            self.race.remove(branch)
            self.branches[branch] = DESCENDANT
            raise GitHubAPIError(422, "Reference already exists")
        self.branches[branch] = payload["sha"]
        return {"ref": payload["ref"]}


def test_validate_merge_event_freezes_head_and_merge_shas() -> None:
    pr = pull_request()
    snapshot = validate_merge_event(event(pr), pr, repository=REPOSITORY)
    assert snapshot.source_sha == HEAD
    assert snapshot.merge_sha == MERGE
    plans = plan_branches(snapshot)
    assert [(plan.name, plan.source_sha, plan.kind) for plan in plans] == [
        ("release-1.14.1", HEAD, "patch"),
        ("release-1.15.0", MERGE, "minor"),
    ]


def test_patch_merge_only_creates_next_patch() -> None:
    pr = pull_request(source="release-1.14.1")
    snapshot = validate_merge_event(event(pr), pr, repository=REPOSITORY)
    assert [(plan.name, plan.source_sha) for plan in plan_branches(snapshot)] == [("release-1.14.2", HEAD)]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda pr: pr.update(merged=False), "without a merge"),
        (lambda pr: pr["base"].update(ref="release-1.14.0"), "target is not main"),
        (lambda pr: pr["head"].update(ref="feature/release-1.14.0"), "not a release branch"),
        (lambda pr: pr["head"]["repo"].update(full_name="someone/fork"), "source"),
    ],
)
def test_rejects_non_release_or_unmerged_closures(mutate, message: str) -> None:
    pr = pull_request()
    mutate(pr)
    with pytest.raises(BranchAutomationError, match=message):
        validate_merge_event(event(pr), pr, repository=REPOSITORY)


def test_rejects_stale_event_snapshot() -> None:
    live = pull_request()
    supplied = pull_request(head_sha=OTHER)
    with pytest.raises(BranchAutomationError, match="stale"):
        validate_merge_event(event(supplied), live, repository=REPOSITORY)


def test_process_event_creates_both_branches_without_publishing() -> None:
    pr = pull_request()
    client = FakeClient(pr)
    report = process_event(event(pr), client, repository=REPOSITORY, protection_verifier=lambda *_: True)
    assert [item["branch"] for item in report["branches"]] == ["release-1.14.1", "release-1.15.0"]
    assert client.branches == {"release-1.14.1": HEAD, "release-1.15.0": MERGE}
    assert all(item["status"] == "verified" and item["owner"] == "LE-3344" for item in report["branches"])
    assert all(path.endswith("/git/refs") for path, _ in client.posts)


def test_protection_preflight_completes_before_any_branch_write() -> None:
    pr = pull_request()
    client = FakeClient(pr)

    def verify(_repository: str, branch: str) -> bool:
        return branch != "release-1.15.0"

    with pytest.raises(BranchAutomationError, match="release protection verification failed"):
        process_event(event(pr), client, repository=REPOSITORY, protection_verifier=verify)
    assert client.posts == []


def test_post_create_protection_failure_reports_retained_branch() -> None:
    pr = pull_request()
    client = FakeClient(pr)
    calls: list[str] = []

    def verify(_repository: str, branch: str) -> bool:
        calls.append(branch)
        return len(calls) <= 2

    with pytest.raises(BranchAutomationError) as raised:
        process_event(event(pr), client, repository=REPOSITORY, protection_verifier=verify)

    report = json.loads(str(raised.value))
    branch = report["branches"][0]
    assert branch["branch"] == "release-1.14.1"
    assert branch["source_sha"] == HEAD
    assert branch["action"] == "created"
    assert branch["status"] == "verification_failed"
    assert "post-create protection verification failed" in report["errors"][0]
    assert client.branches["release-1.14.1"] == HEAD


def test_cli_emits_structured_post_create_failure_report(tmp_path: Path, monkeypatch, capsys) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event()))
    client = FakeClient(pull_request())
    calls: list[str] = []

    def verify(_repository: str, branch: str) -> bool:
        calls.append(branch)
        return len(calls) <= 2

    monkeypatch.setattr(branch_cli, "HTTPGitHubClient", lambda _token: client)
    monkeypatch.setattr(branch_cli, "command_verifier", lambda _bridge: verify)
    monkeypatch.setenv("RELEASE_PROTECTION_BRIDGE", '["fixture-verifier"]')

    result = branch_cli.main(["--event", str(event_path), "--repository", REPOSITORY])
    captured = capsys.readouterr()

    assert result == 1
    report = json.loads(captured.out)
    branch = report["branches"][0]
    assert branch["branch"] == "release-1.14.1"
    assert branch["source_sha"] == HEAD
    assert branch["action"] == "created"
    assert branch["status"] == "verification_failed"
    assert "structured report emitted" in captured.err
    assert client.branches["release-1.14.1"] == HEAD


def test_repeated_event_preserves_exact_branches() -> None:
    pr = pull_request()
    client = FakeClient(pr, branches={"release-1.14.1": HEAD, "release-1.15.0": MERGE})
    report = process_event(event(pr), client, repository=REPOSITORY, protection_verifier=lambda *_: True)
    assert [item["action"] for item in report["branches"]] == ["preserved", "preserved"]
    assert client.posts == []


def test_unrelated_event_is_ignored_without_client_access() -> None:
    pr = pull_request(source="feature/change")

    class NoNetworkClient:
        def get(self, path: str):
            msg = f"unexpected GET {path}"
            raise AssertionError(msg)

    report = process_event(event(pr), NoNetworkClient(), repository=REPOSITORY)
    assert report["status"] == "ignored"
    assert report["branches"] == []


def test_protection_bridge_receives_json_on_stdin() -> None:
    verifier = command_verifier(
        json.dumps(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys; payload=json.load(sys.stdin); "
                    "print(json.dumps({'verified': payload['branch']=='release-1.14.1'}))"
                ),
            ]
        )
    )
    assert verifier(REPOSITORY, "release-1.14.1") is True
    assert verifier(REPOSITORY, "release-1.15.0") is False


def test_cli_matches_workflow_invocation_and_ignores_unrelated_event(tmp_path: Path) -> None:
    workflow = Path(__file__).resolve().parents[2] / ".github/workflows/create-next-release-branches.yml"
    assert "python -m scripts.ci.coordinated_release.branches" in workflow.read_text()
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event(pull_request(source="feature/change"))))
    result = subprocess.run(  # noqa: S603 - fixed local Python module invocation
        [
            sys.executable,
            "-m",
            "scripts.ci.coordinated_release.branches",
            "--event",
            str(event_path),
            "--repository",
            REPOSITORY,
        ],
        cwd=workflow.parents[2],
        env={**os.environ, "GITHUB_TOKEN": "", "RELEASE_PROTECTION_BRIDGE": ""},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "ignored"


def test_cli_requires_protection_bridge_before_eligible_network_access(tmp_path: Path) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event()))
    result = subprocess.run(  # noqa: S603 - fixed local Python module invocation
        [
            sys.executable,
            "-m",
            "scripts.ci.coordinated_release.branches",
            "--event",
            str(event_path),
            "--repository",
            REPOSITORY,
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "GITHUB_TOKEN": "", "RELEASE_PROTECTION_BRIDGE": ""},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "RELEASE_PROTECTION_BRIDGE is required" in result.stderr
    assert "GITHUB_TOKEN is required" not in result.stderr


def test_existing_descendant_is_preserved_and_race_is_reconciled() -> None:
    plan = plan_branches(validate_merge_event(event(), pull_request(), repository=REPOSITORY))[0]
    client = FakeClient(pull_request(), race={plan.name})
    assert ensure_branch(client, REPOSITORY, plan) == "preserved"
    assert client.branches[plan.name] == DESCENDANT


def test_existing_advanced_unrelated_branch_is_not_reset() -> None:
    plan = plan_branches(validate_merge_event(event(), pull_request(), repository=REPOSITORY))[0]
    client = FakeClient(pull_request(), branches={plan.name: OTHER})
    with pytest.raises(BranchDiscrepancy, match="does not descend"):
        ensure_branch(client, REPOSITORY, plan)
    assert client.branches[plan.name] == OTHER
    assert client.posts == []


def test_authentication_error_is_not_treated_as_missing_branch() -> None:
    plan = plan_branches(validate_merge_event(event(), pull_request(), repository=REPOSITORY))[0]

    class UnauthorizedClient(FakeClient):
        def get(self, _path: str) -> dict[str, Any]:
            raise GitHubAPIError(403, "forbidden")

    client = UnauthorizedClient(pull_request())
    with pytest.raises(GitHubAPIError, match="403"):
        ensure_branch(client, REPOSITORY, plan)
    assert client.posts == []


def test_invalid_repository_identity_is_rejected() -> None:
    pr = pull_request()
    with pytest.raises(BranchAutomationError, match="repository"):
        validate_merge_event(event(pr), pr, repository="langflow-ai/other")


def test_workflow_report_capture_preserves_cli_failure(tmp_path):
    """Execute the real shell block so tee cannot conceal protection failures."""
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((root / ".github/workflows/create-next-release-branches.yml").read_text())
    step = next(s for s in workflow["jobs"]["create"]["steps"] if s["name"] == "Create immutable next release branches")
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event()))
    (tmp_path / "python").symlink_to(sys.executable)
    env = {
        "PATH": f"{tmp_path}:/usr/bin:/bin",
        "PYTHONPATH": str(root),
        "GITHUB_EVENT_PATH": str(event_path),
        "GITHUB_REPOSITORY": REPOSITORY,
    }
    completed = subprocess.run(  # noqa: S603 - repository workflow block with isolated event/environment.
        ["/bin/bash", "-e", "-c", step["run"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "RELEASE_PROTECTION_BRIDGE is required" in completed.stderr
    assert (tmp_path / "release-branch-report.json").exists()
