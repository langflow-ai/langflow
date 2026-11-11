"""Coordinate trusted OSS next-release branch creation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .branch_client import (
    BranchDiscrepancy,
    GitHubAPIError,
    GitHubClient,
    HTTPGitHubClient,
    command_verifier,
    ensure_branch,
    verify_protection,
)
from .branch_events import (
    BranchAutomationError,
    BranchPlan,
    MergeSnapshot,
    ignore_reason,
    plan_branches,
    validate_merge_event,
)


class BranchReportError(BranchAutomationError):
    """A branch operation failed after producing a reconciliation report."""

    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(json.dumps(report, sort_keys=True))


__all__ = [
    "BranchAutomationError",
    "BranchDiscrepancy",
    "BranchPlan",
    "BranchReportError",
    "GitHubAPIError",
    "GitHubClient",
    "HTTPGitHubClient",
    "MergeSnapshot",
    "ensure_branch",
    "ignore_reason",
    "plan_branches",
    "process_event",
    "validate_merge_event",
    "verify_protection",
]


def process_event(
    event: dict[str, Any],
    client: GitHubClient,
    *,
    repository: str,
    target_branch: str = "main",
    protection_verifier: Any | None = None,
) -> dict[str, Any]:
    """Reconcile one merge event, ignoring unrelated events before network I/O."""
    reason = ignore_reason(event, repository=repository, target_branch=target_branch)
    if reason is not None:
        return {"status": "ignored", "repository": repository, "reason": reason, "branches": []}
    if protection_verifier is None:
        msg = "release protection verifier is required before branch writes"
        raise BranchAutomationError(msg)
    pr_number = event["pull_request"].get("number")
    if not isinstance(pr_number, int):
        msg = "event pull request number is required"
        raise BranchAutomationError(msg)
    live = client.get(f"/repos/{repository}/pulls/{pr_number}")
    snapshot = validate_merge_event(event, live, repository=repository, target_branch=target_branch)
    plans = plan_branches(snapshot)
    for plan in plans:
        verify_protection(repository, plan.name, protection_verifier)
    results: list[dict[str, str]] = []
    errors: list[str] = []
    for plan in plans:
        try:
            action = ensure_branch(client, repository, plan)
        except BranchDiscrepancy as error:
            errors.append(str(error))
        except BranchAutomationError as error:
            errors.append(f"branch operation failed for {plan.name}: {error}")
            continue
        try:
            # Re-check after ref creation so the bridge can verify the concrete
            # branch against the approved wildcard/ruleset coverage.
            protection = verify_protection(repository, plan.name, protection_verifier)
            results.append({"branch": plan.name, "source_sha": plan.source_sha, "action": action, **protection})
        except BranchAutomationError as error:
            # Never roll back a ref after it was created or preserved. Return
            # its identity so a protected operator can reconcile the failure.
            results.append(
                {
                    "branch": plan.name,
                    "source_sha": plan.source_sha,
                    "action": action,
                    "status": "verification_failed",
                    "error": str(error),
                }
            )
            errors.append(f"post-create protection verification failed for {plan.name}: {error}")
    report = {
        "status": "processed",
        "repository": repository,
        "pull_request": snapshot.pull_request_number,
        "source_branch": snapshot.source_branch,
        "source_sha": snapshot.source_sha,
        "merge_sha": snapshot.merge_sha,
        "branches": results,
        "errors": errors,
    }
    if errors:
        raise BranchReportError(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--target-branch", default="main")
    args = parser.parse_args(argv)
    if not args.repository:
        parser.error("--repository or GITHUB_REPOSITORY is required")
    try:
        event = json.loads(args.event.read_text())
        reason = ignore_reason(event, repository=args.repository, target_branch=args.target_branch)
        if reason is not None:
            print(json.dumps({"status": "ignored", "repository": args.repository, "reason": reason, "branches": []}))
            return 0
        bridge = os.environ.get("RELEASE_PROTECTION_BRIDGE")
        if not bridge:
            msg = "RELEASE_PROTECTION_BRIDGE is required before branch writes"
            raise BranchAutomationError(msg)
        report = process_event(
            event,
            HTTPGitHubClient(os.environ.get("GITHUB_TOKEN", "")),
            repository=args.repository,
            target_branch=args.target_branch,
            protection_verifier=command_verifier(bridge),
        )
    except BranchReportError as error:
        print(json.dumps(error.report, indent=2, sort_keys=True))
        print("release branch automation failed; structured report emitted", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError, BranchAutomationError) as error:
        print(f"release branch automation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
