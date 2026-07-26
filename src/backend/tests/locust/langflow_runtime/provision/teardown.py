"""Idempotent reverse teardown of suite-tagged resources."""

from __future__ import annotations

import time
from typing import Any

from tests.locust.langflow_runtime.provision.api import ProvisionApiError, ProvisionHttp
from tests.locust.langflow_runtime.provision.state import resource_tagged_for_env


class TeardownError(RuntimeError):
    """Raised when teardown would delete an untagged or foreign resource."""


def assert_safe_to_delete(resource: dict[str, Any], env_id: str) -> None:
    """Pure guard used by unit tests and teardown — refuse untagged resources."""
    if not resource_tagged_for_env(resource, env_id):
        msg = (
            f"refusing to delete {resource.get('kind')}:{resource.get('id')} "
            f"(env_id={resource.get('env_id')!r} != suite env_id={env_id!r})"
        )
        raise TeardownError(msg)


def _find_resource(state: dict[str, Any], kind: str, resource_id: str) -> dict[str, Any] | None:
    """Return a registered ownership record, or None when the registry has no match.

    Never synthesize a tagged resource from teardown_order alone — that would
    defeat assert_safe_to_delete for untagged / foreign ids.
    """
    for resource in state.get("resources") or []:
        if resource.get("kind") == kind and str(resource.get("id")) == str(resource_id):
            return resource
    return None


def _delete_one(http: ProvisionHttp, kind: str, resource_id: str) -> str:
    try:
        if kind == "flow":
            http.delete_flow(resource_id)
        elif kind == "project":
            http.delete_project(resource_id)
        elif kind == "api_key":
            http.delete_api_key(resource_id)
        elif kind == "kb":
            http.delete_knowledge_base(resource_id)
        elif kind == "user":
            http.delete_user(resource_id)
        else:
            return f"skip unknown kind {kind}"
        return "deleted"
    except ProvisionApiError as exc:
        if exc.status_code in {404, 410}:
            return "missing"
        raise


def teardown_state(
    http: ProvisionHttp,
    state: dict[str, Any],
    *,
    retries: int = 3,
    retry_delay_s: float = 0.5,
) -> list[dict[str, Any]]:
    """Delete resources in teardown_order; missing resources count as success."""
    env_id = str(state["env_id"])
    results: list[dict[str, Any]] = []
    order = list(state.get("teardown_order") or [])

    for token in order:
        if ":" not in token:
            results.append({"token": token, "status": "invalid_token"})
            continue
        kind, resource_id = token.split(":", 1)
        resource = _find_resource(state, kind, resource_id)
        if resource is None:
            results.append(
                {
                    "token": token,
                    "status": "refused",
                    "error": "no ownership record in state.resources",
                }
            )
            continue
        try:
            assert_safe_to_delete(resource, env_id)
        except TeardownError as exc:
            results.append({"token": token, "status": "refused", "error": str(exc)})
            continue

        status = "error"
        last_error: str | None = None
        for attempt in range(retries):
            try:
                status = _delete_one(http, kind, resource_id)
                last_error = None
                break
            except Exception as exc:
                last_error = str(exc)
                if attempt + 1 < retries:
                    time.sleep(retry_delay_s)
        results.append({"token": token, "status": status, "error": last_error})
    return results
