"""Preflight health and auth checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def check_health(host: str, *, timeout_s: float = 10.0) -> CheckResult:
    url = f"{host.rstrip('/')}/health"
    try:
        response = httpx.get(url, timeout=timeout_s)
    except httpx.HTTPError as exc:
        return CheckResult(name="health", ok=False, detail=str(exc))
    if response.status_code != 200:
        return CheckResult(name="health", ok=False, detail=f"HTTP {response.status_code}")
    return CheckResult(name="health", ok=True, detail="ok")


def check_auth(host: str, api_key: str, *, timeout_s: float = 10.0) -> CheckResult:
    """Verify API key auth against a lightweight authenticated endpoint."""
    url = f"{host.rstrip('/')}/api/v1/users/whoami"
    try:
        response = httpx.get(url, headers={"x-api-key": api_key}, timeout=timeout_s)
    except httpx.HTTPError as exc:
        return CheckResult(name="auth", ok=False, detail=str(exc))
    if response.status_code in {401, 403}:
        return CheckResult(name="auth", ok=False, detail=f"HTTP {response.status_code}")
    if response.status_code == 404:
        return CheckResult(name="auth", ok=False, detail="HTTP 404 from /users/whoami")
    if response.status_code >= 400:
        return CheckResult(name="auth", ok=False, detail=f"HTTP {response.status_code}")
    return CheckResult(name="auth", ok=True, detail="ok")


def check_fixture_hashes(state: dict[str, Any] | None, fixture_index: dict[str, Any] | None) -> CheckResult:
    """Compare provision state fixture hashes against fixture_index when present."""
    if not state or not fixture_index:
        return CheckResult(name="fixture_index", ok=True, detail="skipped (missing state or index)")

    state_hashes = state.get("fixture_hashes") or state.get("fixture_sha256")
    if not state_hashes:
        return CheckResult(name="fixture_index", ok=True, detail="skipped (no hashes in state)")

    index_flows = {flow.get("id"): flow for flow in fixture_index.get("flows", []) if isinstance(flow, dict)}
    mismatches: list[str] = []
    if isinstance(state_hashes, dict):
        for fixture_id, expected in state_hashes.items():
            flow = index_flows.get(fixture_id)
            if flow is None:
                mismatches.append(f"{fixture_id}: missing from index")
                continue
            actual = flow.get("fixture_sha256")
            if actual and str(actual) != str(expected):
                mismatches.append(f"{fixture_id}: state={expected} index={actual}")
    if mismatches:
        return CheckResult(name="fixture_index", ok=False, detail="; ".join(mismatches))
    return CheckResult(name="fixture_index", ok=True, detail="ok")
