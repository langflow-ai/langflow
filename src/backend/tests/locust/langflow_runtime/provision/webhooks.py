"""Webhook flow-copy provisioning and one-shot subscribe-before-POST validation."""

from __future__ import annotations

from typing import Any

from tests.locust.langflow_runtime.clients.webhooks import WebhookCopy, WebhooksClient
from tests.locust.langflow_runtime.provision.api import ProvisionHttp
from tests.locust.langflow_runtime.provision.flows import import_flow, load_fixture_index
from tests.locust.langflow_runtime.v1_contracts import DEFAULT_WEBHOOK_PAYLOAD


def webhook_copy_count(entry: dict[str, Any], *, profile_max: int | None = None) -> int:
    count = int(entry.get("webhook_copy_count") or 0)
    if count <= 0 and "webhook" in (entry.get("supported_protocols") or []):
        count = 1
    if profile_max is not None:
        count = max(count, profile_max)
    return count


def provision_webhook_copies(
    http: ProvisionHttp,
    state: dict[str, Any],
    *,
    flow_ids: list[str],
    index: dict[str, Any] | None = None,
    profile_max: int | None = None,
) -> list[dict[str, Any]]:
    """Create N flow copies for webhook fixtures; store under flows[*].copies and webhooks.copies."""
    idx = index or load_fixture_index()
    by_id = {str(e["id"]): e for e in idx.get("flows", [])}
    all_copies: list[dict[str, Any]] = []
    flows = state.setdefault("flows", {})

    for fixture_id in flow_ids:
        entry = by_id.get(fixture_id)
        if entry is None:
            continue
        n = webhook_copy_count(entry, profile_max=profile_max)
        if n <= 0:
            continue
        copies: list[dict[str, Any]] = []
        last_record: dict[str, Any] | None = None
        for i in range(n):
            record = import_flow(http, state, entry, copy_index=i)
            last_record = record
            copy = {
                "flow_id": record["flow_id"],
                "endpoint_name": record["endpoint_name"],
                "project_id": record["project_id"],
                "fixture_id": fixture_id,
                "env_id": state["env_id"],
            }
            copies.append(copy)
            all_copies.append(copy)

        flows[fixture_id] = {
            "flow_id": copies[0]["flow_id"],
            "endpoint_name": copies[0]["endpoint_name"],
            "mcp_action_name": entry.get("mcp_action_name"),
            "fixture_id": fixture_id,
            "fixture_sha256": entry.get("fixture_sha256") or (last_record or {}).get("fixture_sha256"),
            "project_id": copies[0]["project_id"],
            "env_id": state["env_id"],
            "copies": copies,
        }

    state.setdefault("webhooks", {})["copies"] = all_copies
    state["webhooks"]["validated"] = False
    return all_copies


def validate_webhook_subscribe_before_post(
    http: ProvisionHttp,
    state: dict[str, Any],
    *,
    timeout_s: float = 60.0,
) -> bool:
    """One subscribe-before-POST validation; runtime subscriptions remain Locust-owned."""
    api_key = state.get("api_key")
    copies = (state.get("webhooks") or {}).get("copies") or []
    if not api_key or not copies:
        state.setdefault("webhooks", {})["validated"] = False
        state.setdefault("flags", {})["webhook_validated"] = False
        return False

    first = copies[0]
    client = WebhooksClient(
        http._client,
        base_url=http.base_url,
        api_key=str(api_key),
        workload="provision",
        flow_class="webhook",
    )
    result = client.subscribe_post_complete(
        WebhookCopy(flow_id=str(first["flow_id"]), endpoint_name=str(first["endpoint_name"])),
        DEFAULT_WEBHOOK_PAYLOAD,
        timeout_s=timeout_s,
    )
    ok = bool(result.accepted and result.completed and result.error is None)
    state.setdefault("webhooks", {})["validated"] = ok
    state["webhooks"]["last_error"] = result.error
    state.setdefault("flags", {})["webhook_validated"] = ok
    return ok
