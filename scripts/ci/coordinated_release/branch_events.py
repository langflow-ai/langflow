"""Pure event validation and next-branch planning for release merges."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SHA = re.compile(r"^[0-9a-f]{40}$")
RELEASE_BRANCH = re.compile(r"^release-(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class BranchAutomationError(RuntimeError):
    """A merge event cannot be trusted."""


@dataclass(frozen=True)
class MergeSnapshot:
    repository: str
    pull_request_id: int
    pull_request_number: int
    source_branch: str
    source_sha: str
    merge_sha: str
    target_branch: str = "main"


@dataclass(frozen=True)
class BranchPlan:
    name: str
    source_sha: str
    kind: str


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        msg = f"{field} must be a non-empty string"
        raise BranchAutomationError(msg)
    return value


def _sha(value: Any, field: str) -> str:
    value = _text(value, field).lower()
    if not SHA.fullmatch(value):
        msg = f"{field} must be a full lowercase Git SHA"
        raise BranchAutomationError(msg)
    return value


def _repo(document: dict[str, Any], field: str) -> str:
    value = document.get("full_name")
    if value is None:
        value = document.get("repo")
    if isinstance(value, dict):
        value = value.get("full_name")
    return _text(value, field)


def _pull_request_fields(document: dict[str, Any], *, prefix: str) -> tuple[str, str, str, str, str, str]:
    base = document.get("base")
    head = document.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        msg = f"{prefix} pull request base/head are required"
        raise BranchAutomationError(msg)
    return (
        _repo(base, f"{prefix}.base"),
        _text(base.get("ref"), f"{prefix}.base.ref"),
        _repo(head, f"{prefix}.head"),
        _text(head.get("ref"), f"{prefix}.head.ref"),
        _sha(head.get("sha"), f"{prefix}.head.sha"),
        _sha(document.get("merge_commit_sha"), f"{prefix}.merge_commit_sha"),
    )


def ignore_reason(event: dict[str, Any], *, repository: str, target_branch: str = "main") -> str | None:
    """Return a no-op reason for events that cannot be release merges."""
    if event.get("action") != "closed":
        return "pull request is not closed"
    event_repo = event.get("repository")
    if not isinstance(event_repo, dict) or event_repo.get("full_name") != repository:
        return "event repository is not this repository"
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        msg = "event.pull_request is required"
        raise BranchAutomationError(msg)
    if pull_request.get("merged") is not True:
        return "pull request was closed without a merge"
    base = pull_request.get("base")
    head = pull_request.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        msg = "event pull request base/head are required"
        raise BranchAutomationError(msg)
    if base.get("ref") != target_branch:
        return "pull request target is not main"
    if _repo(base, "event.pull_request.base") != repository:
        return "pull request base repository is not this repository"
    if _repo(head, "event.pull_request.head") != repository:
        return "pull request source is from another repository"
    if RELEASE_BRANCH.fullmatch(str(head.get("ref", ""))) is None:
        return "pull request source is not a release branch"
    return None


def validate_merge_event(
    event: dict[str, Any], live: dict[str, Any], *, repository: str, target_branch: str = "main"
) -> MergeSnapshot:
    """Validate event and re-fetched PR identity, returning immutable source SHAs."""
    reason = ignore_reason(event, repository=repository, target_branch=target_branch)
    if reason is not None:
        raise BranchAutomationError(reason)
    event_pr = event["pull_request"]
    if not isinstance(live, dict):
        msg = "GitHub pull request response must be an object"
        raise BranchAutomationError(msg)
    event_id = event_pr.get("id")
    live_id = live.get("id")
    if not isinstance(event_id, int) or not isinstance(live_id, int) or event_id != live_id:
        msg = "pull request identity changed between event and API snapshot"
        raise BranchAutomationError(msg)
    event_number = event_pr.get("number")
    live_number = live.get("number")
    if not isinstance(event_number, int) or event_number != live_number:
        msg = "pull request number changed between event and API snapshot"
        raise BranchAutomationError(msg)
    event_fields = _pull_request_fields(event_pr, prefix="event.pull_request")
    live_fields = _pull_request_fields(live, prefix="live.pull_request")
    if event_fields != live_fields:
        msg = "merge event is stale or differs from live pull request"
        raise BranchAutomationError(msg)
    event_base, event_base_ref, event_head_repo, event_head_ref, event_head_sha, event_merge_sha = event_fields
    live_base, live_base_ref, live_head_repo, live_head_ref, _, _ = live_fields
    if event_base != repository or live_base != repository:
        msg = "pull request base repository does not match current repository"
        raise BranchAutomationError(msg)
    if event_base_ref != target_branch or live_base_ref != target_branch:
        msg = "pull request was not merged into the default main branch"
        raise BranchAutomationError(msg)
    if event_head_repo != repository or live_head_repo != repository:
        msg = "release source must be a branch in this repository"
        raise BranchAutomationError(msg)
    if live.get("merged") is not True:
        msg = "live pull request is no longer merged"
        raise BranchAutomationError(msg)
    if RELEASE_BRANCH.fullmatch(event_head_ref) is None or live_head_ref != event_head_ref:
        msg = "merged source must be exactly release-X.Y.Z"
        raise BranchAutomationError(msg)
    return MergeSnapshot(
        repository=repository,
        pull_request_id=live_id,
        pull_request_number=live_number,
        source_branch=event_head_ref,
        source_sha=event_head_sha,
        merge_sha=event_merge_sha,
        target_branch=target_branch,
    )


def plan_branches(snapshot: MergeSnapshot) -> tuple[BranchPlan, ...]:
    match = RELEASE_BRANCH.fullmatch(snapshot.source_branch)
    if match is None:
        msg = "snapshot source branch is not a release branch"
        raise BranchAutomationError(msg)
    major, minor, patch = (int(value) for value in match.groups())
    plans = [BranchPlan(f"release-{major}.{minor}.{patch + 1}", snapshot.source_sha, "patch")]
    if patch == 0:
        plans.append(BranchPlan(f"release-{major}.{minor + 1}.0", snapshot.merge_sha, "minor"))
    return tuple(plans)
