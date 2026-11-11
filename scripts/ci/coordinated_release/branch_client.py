"""GitHub ref operations and release-protection bridge adapter."""

from __future__ import annotations

import json
import subprocess
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from .branch_events import SHA, BranchAutomationError, BranchPlan

HTTP_NOT_FOUND = 404


class BranchDiscrepancyError(BranchAutomationError):
    """An existing branch does not descend from the required source."""


BranchDiscrepancy = BranchDiscrepancyError


class GitHubAPIError(BranchAutomationError):
    """An authenticated GitHub request failed."""

    def __init__(self, status: int, message: str):
        super().__init__(f"GitHub API HTTP {status}: {message}")
        self.status = status


class GitHubClient(Protocol):
    def get(self, path: str) -> dict[str, Any]: ...

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class HTTPGitHubClient:
    """Small stdlib GitHub client; credentials never enter result documents."""

    def __init__(self, token: str, *, api_url: str = "https://api.github.com"):
        parsed = urlsplit(api_url)
        if not token:
            msg = "GITHUB_TOKEN is required"
            raise BranchAutomationError(msg)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
            msg = "GitHub API URL must be HTTPS without credentials or query parameters"
            raise BranchAutomationError(msg)
        self.token = token
        self.api_url = api_url.rstrip("/")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not path.startswith("/") or path.startswith("//"):
            msg = "GitHub API path must be relative"
            raise BranchAutomationError(msg)
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(  # noqa: S310 - URL is validated as HTTPS above
            self.api_url + path,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "langflow-release-branch-automation",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS API host
                body = response.read()
        except HTTPError as error:
            try:
                detail = json.loads(error.read()).get("message", error.reason)
            except (OSError, json.JSONDecodeError):
                detail = str(error.reason)
            raise GitHubAPIError(error.code, str(detail)) from error
        except URLError as error:
            msg = f"GitHub API unavailable: {error.reason}"
            raise BranchAutomationError(msg) from error
        if not body:
            return {}
        try:
            value = json.loads(body)
        except json.JSONDecodeError as error:
            msg = "GitHub API returned invalid JSON"
            raise BranchAutomationError(msg) from error
        if not isinstance(value, dict):
            msg = "GitHub API returned an unexpected document"
            raise BranchAutomationError(msg)
        return value

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or SHA.fullmatch(value.lower()) is None:
        msg = f"{field} must be a full lowercase Git SHA"
        raise BranchAutomationError(msg)
    return value.lower()


def ensure_branch(client: GitHubClient, repository: str, plan: BranchPlan) -> str:
    """Create a branch, or preserve an existing descendant; never force-update it."""
    path = f"/repos/{repository}/git/ref/heads/{quote(plan.name, safe='')}"
    try:
        current = client.get(path)
    except GitHubAPIError as error:
        if error.status != HTTP_NOT_FOUND:
            raise
        try:
            client.post(f"/repos/{repository}/git/refs", {"ref": f"refs/heads/{plan.name}", "sha": plan.source_sha})
        except GitHubAPIError as race:
            if race.status not in (409, 422):
                raise
            current = client.get(path)
        else:
            return "created"
    current_sha = _sha(current.get("object", {}).get("sha"), f"{plan.name}.sha")
    if current_sha == plan.source_sha:
        return "preserved"
    comparison = client.get(f"/repos/{repository}/compare/{plan.source_sha}...{quote(plan.name, safe='')}")
    status = comparison.get("status")
    base_sha = comparison.get("base_commit", {}).get("sha")
    if status in {"ahead", "identical"} and isinstance(base_sha, str) and base_sha.lower() == plan.source_sha:
        return "preserved"
    msg = f"existing {plan.name} at {current_sha} does not descend from required {plan.source_sha}"
    raise BranchDiscrepancy(msg)


def verify_protection(repository: str, branch: str, verifier: Any) -> dict[str, str]:
    """Verify release-protection policy through the configured JSON bridge."""
    if verifier(repository, branch) is not True:
        msg = f"release protection verification failed for {branch}"
        raise BranchAutomationError(msg)
    return {"status": "verified", "owner": "release-protection"}


def command_verifier(command_json: str):
    """Build a no-shell verifier from a JSON argv array."""
    try:
        argv = json.loads(command_json)
    except json.JSONDecodeError as error:
        msg = "RELEASE_PROTECTION_BRIDGE must be a JSON argv array"
        raise BranchAutomationError(msg) from error
    if not isinstance(argv, list) or not argv or not all(isinstance(part, str) and part for part in argv):
        msg = "RELEASE_PROTECTION_BRIDGE must be a non-empty JSON argv array"
        raise BranchAutomationError(msg)

    def verify(repository: str, branch: str) -> bool:
        try:
            completed = subprocess.run(  # noqa: S603 - configured argv, no shell
                argv,
                input=json.dumps({"repository": repository, "branch": branch}, separators=(",", ":")) + "\n",
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if completed.returncode != 0:
            return False
        try:
            result = json.loads(completed.stdout or "false")
        except json.JSONDecodeError:
            return False
        return result is True or (isinstance(result, dict) and result.get("verified") is True)

    return verify
