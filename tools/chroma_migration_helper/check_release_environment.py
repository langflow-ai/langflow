"""Fail closed unless GitHub confirms the helper environment requires review.

This is a read-only preflight, not environment provisioning. An administrator
must configure required reviewers first and allow the workflow token Actions
read access. A missing environment, inaccessible API or malformed response stops
publication instead of allowing GitHub to create an unprotected environment.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

ENVIRONMENT = "chroma-migration-helper-release"
ENDPOINT = f"repos/langflow-ai/langflow/environments/{ENVIRONMENT}"
SETUP_REQUIRED = (
    "Helper publication is blocked: configure chroma-migration-helper-release with required human reviewers, "
    "prevent self-review and disable administrator bypass, "
    "and permit the workflow GITHUB_TOKEN to read the environment with actions: read. "
    "This check does not create or change GitHub environments."
)


def require_reviewers(payload: object) -> None:
    """Require the configured release environment's approval controls before signing."""
    if not isinstance(payload, dict) or payload.get("name") != ENVIRONMENT:
        raise ValueError(SETUP_REQUIRED)
    if payload.get("can_admins_bypass") is not False:
        raise ValueError(SETUP_REQUIRED)
    rules = payload.get("protection_rules")
    if not isinstance(rules, list):
        raise ValueError(SETUP_REQUIRED)  # noqa: TRY004 -- invalid API data is a failed publication precondition
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != "required_reviewers":
            continue
        if rule.get("prevent_self_review") is not True:
            continue
        reviewers = rule.get("reviewers")
        if not isinstance(reviewers, list) or not reviewers:
            continue
        if all(
            isinstance(entry, dict)
            and entry.get("type") in {"User", "Team"}
            and isinstance(entry.get("reviewer"), dict)
            and (entry["type"] == "Team" or entry["reviewer"].get("type") == "User")
            and type(entry["reviewer"].get("id")) is int
            and entry["reviewer"]["id"] > 0
            for entry in reviewers
        ):
            return
    raise ValueError(SETUP_REQUIRED)


def check_environment() -> None:
    """Verify that the helper release environment enforces the expected publication protections."""
    try:
        executable = shutil.which("gh")
        if executable is None:
            raise ValueError(SETUP_REQUIRED)
        result = subprocess.run(  # noqa: S603 -- fixed read-only GitHub endpoint, no user-supplied command
            [
                executable,
                "api",
                "--hostname",
                "github.com",
                "--method",
                "GET",
                "--header",
                "Accept: application/vnd.github+json",
                "--header",
                "X-GitHub-Api-Version: 2022-11-28",
                ENDPOINT,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        require_reviewers(json.loads(result.stdout))
    except (OSError, subprocess.SubprocessError, ValueError, TypeError) as exc:
        raise ValueError(SETUP_REQUIRED) from exc


if __name__ == "__main__":
    try:
        check_environment()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)  # noqa: T201 -- clear CI setup diagnostic, no API body or credentials
        sys.exit(1)
