"""MCP Locust user."""

from __future__ import annotations

from datetime import UTC, datetime

from locust import task

from tests.locust.langflow_runtime.config.naming import metric_name
from tests.locust.langflow_runtime.flows.defaults import DEFAULT_PASSTHROUGH_INPUT
from tests.locust.langflow_runtime.metrics.lifecycle import lifecycle_timer
from tests.locust.langflow_runtime.metrics.registry import TrackedMcpCall
from tests.locust.langflow_runtime.users.base import PerfBaseUser


class McpUser(PerfBaseUser):
    weight = 1
    workload_name = "mcp"
    flow_class = "passthrough"

    @task
    def tools_call(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        flow = self.require_flow("perf_passthrough")
        client = self.mcp_client()
        if flow is None or client is None:
            return

        tool_name = str(flow.get("mcp_action_name") or "perf_passthrough")
        name = metric_name("mcp", "full_lifecycle", self.workload_name, self.flow_class)
        started = datetime.now(UTC)
        success = False
        try:
            with lifecycle_timer(name):
                client.full_lifecycle_call(tool_name, {"input_value": DEFAULT_PASSTHROUGH_INPUT})
            success = True
        finally:
            self.registry.register_mcp(
                TrackedMcpCall(
                    tool_name=tool_name,
                    started_at=started,
                    finished_at=datetime.now(UTC),
                    success=success,
                )
            )
