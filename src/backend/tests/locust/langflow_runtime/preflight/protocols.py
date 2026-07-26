"""Preflight one-transaction protocol checks."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from tests.locust.langflow_runtime.clients.mcp_streamable import McpStreamableClient
from tests.locust.langflow_runtime.clients.webhooks import WebhookCopy, WebhooksClient
from tests.locust.langflow_runtime.clients.workflows import WorkflowsClient
from tests.locust.langflow_runtime.contracts import DEFAULT_WEBHOOK_PAYLOAD
from tests.locust.langflow_runtime.flows.defaults import DEFAULT_PASSTHROUGH_INPUT
from tests.locust.langflow_runtime.preflight.health import CheckResult
from tests.locust.langflow_runtime.users.base import require_flow


def _http(host: str) -> httpx.Client:
    return httpx.Client(base_url=host.rstrip("/"), timeout=60.0)


def check_mcp(host: str, state: dict[str, Any], *, timeout_s: float = 60.0) -> CheckResult:
    flow = require_flow(state, "perf_passthrough")
    project_id = state.get("project_id")
    api_key = state.get("api_key")
    if flow is None or not project_id or not api_key:
        return CheckResult(name="mcp", ok=True, detail="skipped (missing state)")
    tool_name = str(flow.get("mcp_action_name") or "perf_passthrough")
    with _http(host) as http:
        client = McpStreamableClient(
            http,
            base_url=host.rstrip("/"),
            project_id=str(project_id),
            api_key=str(api_key),
            workload="preflight",
            flow_class="passthrough",
        )
        try:
            client.full_lifecycle_call(tool_name, {"input_value": DEFAULT_PASSTHROUGH_INPUT})
        except Exception as exc:
            return CheckResult(name="mcp", ok=False, detail=str(exc))
    return CheckResult(name="mcp", ok=True, detail="ok")


def check_workflows_sync(host: str, state: dict[str, Any]) -> CheckResult:
    flow = require_flow(state, "perf_passthrough")
    api_key = state.get("api_key")
    if flow is None or not api_key:
        return CheckResult(name="workflows_sync", ok=True, detail="skipped (missing state)")
    with _http(host) as http:
        client = WorkflowsClient(
            http,
            base_url=host.rstrip("/"),
            api_key=str(api_key),
            workload="preflight",
            flow_class="passthrough",
        )
        try:
            client.run_sync(
                flow_id=str(flow["flow_id"]),
                input_value=DEFAULT_PASSTHROUGH_INPUT,
                session_id=f"preflight-{uuid.uuid4().hex[:8]}",
            )
        except Exception as exc:
            return CheckResult(name="workflows_sync", ok=False, detail=str(exc))
    return CheckResult(name="workflows_sync", ok=True, detail="ok")


def check_webhook(host: str, state: dict[str, Any]) -> CheckResult:
    flow = require_flow(state, "perf_webhook_passthrough")
    api_key = state.get("api_key")
    if flow is None or not api_key:
        return CheckResult(name="webhook", ok=True, detail="skipped (missing state)")

    copies_raw = flow.get("copies")
    if isinstance(copies_raw, list) and copies_raw and isinstance(copies_raw[0], dict):
        copy = WebhookCopy(flow_id=str(copies_raw[0]["flow_id"]), endpoint_name=str(copies_raw[0]["endpoint_name"]))
    elif flow.get("flow_id") and flow.get("endpoint_name"):
        copy = WebhookCopy(flow_id=str(flow["flow_id"]), endpoint_name=str(flow["endpoint_name"]))
    else:
        return CheckResult(name="webhook", ok=True, detail="skipped (no copies)")

    with _http(host) as http:
        client = WebhooksClient(
            http,
            base_url=host.rstrip("/"),
            api_key=str(api_key),
            workload="preflight",
            flow_class="passthrough",
        )
        try:
            result = client.subscribe_post_complete(copy, dict(DEFAULT_WEBHOOK_PAYLOAD), timeout_s=60.0)
        except Exception as exc:
            return CheckResult(name="webhook", ok=False, detail=str(exc))
    if result.error or not result.accepted or not result.completed:
        return CheckResult(
            name="webhook",
            ok=False,
            detail=result.error or f"accepted={result.accepted} completed={result.completed}",
        )
    return CheckResult(name="webhook", ok=True, detail="ok")


def run_protocol_checks(host: str, state: dict[str, Any], protocols: list[str]) -> list[CheckResult]:
    results: list[CheckResult] = []
    if "mcp" in protocols:
        results.append(check_mcp(host, state))
    if any(p.startswith("workflows") for p in protocols):
        results.append(check_workflows_sync(host, state))
    if "webhook" in protocols:
        results.append(check_webhook(host, state))
    return results
