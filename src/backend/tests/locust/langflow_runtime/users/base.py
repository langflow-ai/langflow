"""Base Locust user for the performance suite."""

from __future__ import annotations

import uuid
from typing import Any

from locust import FastHttpUser, between

from tests.locust.langflow_runtime.clients.base import ApiClient
from tests.locust.langflow_runtime.clients.mcp_streamable import McpStreamableClient
from tests.locust.langflow_runtime.clients.webhooks import WebhookCopy, WebhookCopyPool, WebhooksClient
from tests.locust.langflow_runtime.clients.workflows import WorkflowsClient
from tests.locust.langflow_runtime.config.context import RunContext
from tests.locust.langflow_runtime.metrics.arrivals import ArrivalAccountant, PacedArrivalScheduler
from tests.locust.langflow_runtime.metrics.registry import get_registry
from tests.locust.langflow_runtime.users.helpers import extract_output_text, require_flow

__all__ = [
    "PerfBaseUser",
    "extract_output_text",
    "get_or_create_arrival_accountant",
    "get_or_create_paced_arrival_scheduler",
    "get_or_create_webhook_pool",
    "parse_kv_metrics",
    "parse_multiproc_header",
    "require_flow",
]


def parse_kv_metrics(text: str, *, prefix: str) -> dict[str, Any] | None:
    """Parse ``prefix:k=v:k=v:...`` style isolator output into a dict."""
    if not text or not text.startswith(f"{prefix}:"):
        return None
    body = text.split("|", 1)[0]
    parts = body.split(":")
    if len(parts) < 2 or parts[0] != prefix:
        return None
    result: dict[str, Any] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            result[key] = int(value)
        else:
            result[key] = value
    return result or None


def parse_multiproc_header(text: str) -> dict[str, Any] | None:
    """Parse ``multiproc:count:codes:ws:elapsed:overlap:vcs:ivcs:seed`` headers."""
    if not text.startswith("multiproc:"):
        return None
    header = text.split("|", 1)[0]
    parts = header.split(":", 8)
    if len(parts) != 9:
        return None
    try:
        return {
            "count": int(parts[1]),
            "overlap_ms": int(parts[5]),
            "vcs": int(parts[6]),
            "ivcs": int(parts[7]),
            "switches": int(parts[6]),
        }
    except ValueError:
        return None


def get_or_create_arrival_accountant(environment: Any) -> ArrivalAccountant:
    accountant = getattr(environment, "arrival_accountant", None)
    if accountant is None:
        accountant = ArrivalAccountant()
        environment.arrival_accountant = accountant
    return accountant


def get_or_create_paced_arrival_scheduler(
    environment: Any,
    *,
    rate_per_s: float,
    allowed_lateness_s: float,
) -> PacedArrivalScheduler:
    scheduler = getattr(environment, "queue_arrival_scheduler", None)
    if scheduler is None:
        scheduler = PacedArrivalScheduler(rate_per_s, allowed_lateness_s=allowed_lateness_s)
        environment.queue_arrival_scheduler = scheduler
    return scheduler


def get_or_create_webhook_pool(environment: Any, state: dict[str, Any] | None) -> WebhookCopyPool | None:
    existing = getattr(environment, "webhook_pool", None)
    if existing is not None:
        return existing
    flow = require_flow(state, "perf_webhook_passthrough")
    if flow is None:
        return None
    copies_raw = flow.get("copies")
    copies: list[WebhookCopy] = []
    if isinstance(copies_raw, list) and copies_raw:
        for item in copies_raw:
            if isinstance(item, dict) and item.get("flow_id") and item.get("endpoint_name"):
                copies.append(WebhookCopy(flow_id=str(item["flow_id"]), endpoint_name=str(item["endpoint_name"])))
    elif flow.get("flow_id") and flow.get("endpoint_name"):
        copies.append(WebhookCopy(flow_id=str(flow["flow_id"]), endpoint_name=str(flow["endpoint_name"])))
    if not copies:
        return None
    pool = WebhookCopyPool(copies)
    environment.webhook_pool = pool
    return pool


class PerfBaseUser(FastHttpUser):
    """Shared base class; subclasses implement category-specific tasks."""

    abstract = True
    workload_name: str = "perf"
    flow_class: str = "passthrough"

    def on_start(self) -> None:
        self.run_context: RunContext | None = getattr(self.environment, "run_context", None)
        self.provision_state: dict[str, Any] | None = None
        self.session_id = f"perf-user-{uuid.uuid4().hex[:12]}"
        self.registry = get_registry()

        if self.run_context is not None:
            self.provision_state = self.run_context.provision_state
            think = self.run_context.profile.workload.think_time
            if think is not None:
                self.wait_time = between(think.min_s, think.max_s).__get__(self, type(self))

    @property
    def api_key(self) -> str | None:
        if not self.provision_state:
            return None
        value = self.provision_state.get("api_key")
        return str(value) if value else None

    @property
    def project_id(self) -> str | None:
        if not self.provision_state:
            return None
        value = self.provision_state.get("project_id")
        if value:
            return str(value)
        flows = self.provision_state.get("flows")
        if isinstance(flows, dict):
            for row in flows.values():
                if isinstance(row, dict) and row.get("project_id"):
                    return str(row["project_id"])
        return None

    @property
    def base_url(self) -> str:
        if self.run_context is not None and self.run_context.host:
            return self.run_context.host.rstrip("/")
        host = getattr(self.environment, "host", None) or ""
        return str(host).rstrip("/")

    def require_flow(self, fixture_id: str) -> dict[str, Any] | None:
        return require_flow(self.provision_state, fixture_id)

    def require_flow_or_fail(self, fixture_id: str) -> dict[str, Any]:
        flow = self.require_flow(fixture_id)
        if flow is None:
            msg = f"provisioned flow {fixture_id!r} missing from state; cannot run {self.__class__.__name__}"
            raise RuntimeError(msg)
        return flow

    def require_workflows_client(self, **kwargs: Any) -> WorkflowsClient:
        client = self.workflows_client(**kwargs)
        if client is None:
            msg = f"workflows client unavailable for {self.__class__.__name__} (missing api_key?)"
            raise RuntimeError(msg)
        return client

    def stop_new_arrivals(self) -> bool:
        return bool(getattr(self.environment, "stop_new_arrivals", False))

    def workflows_client(self, *, workload: str | None = None, flow_class: str | None = None) -> WorkflowsClient | None:
        if not self.api_key:
            return None
        return WorkflowsClient(
            api=ApiClient.from_locust(self.client, base_url=self.base_url, api_key=self.api_key),
            workload=workload or self.workload_name,
            flow_class=flow_class or self.flow_class,
        )

    def mcp_client(self, *, workload: str | None = None, flow_class: str | None = None) -> McpStreamableClient | None:
        if not self.api_key or not self.project_id:
            return None
        return McpStreamableClient(
            api=ApiClient.from_locust(self.client, base_url=self.base_url, api_key=self.api_key),
            project_id=self.project_id,
            workload=workload or self.workload_name,
            flow_class=flow_class or self.flow_class,
        )

    def webhooks_client(self, *, workload: str | None = None, flow_class: str | None = None) -> WebhooksClient | None:
        if not self.api_key:
            return None
        pool = get_or_create_webhook_pool(self.environment, self.provision_state)
        return WebhooksClient(
            api=ApiClient.from_locust(self.client, base_url=self.base_url, api_key=self.api_key),
            workload=workload or self.workload_name,
            flow_class=flow_class or self.flow_class,
            pool=pool,
        )

    def poll_interval_s(self) -> float:
        if self.run_context is None:
            return 0.25
        return float(self.run_context.profile.windows.poll_interval_s)

    def deadline_s(self) -> float:
        if self.run_context is None:
            return 60.0
        return float(self.run_context.profile.safety_limits.drain_timeout_s)
