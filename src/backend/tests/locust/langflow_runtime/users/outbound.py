"""Outbound LLM Locust user."""

from __future__ import annotations

from locust import task

from tests.locust.langflow_runtime.flows.defaults import DEFAULT_OUTBOUND_PROMPT
from tests.locust.langflow_runtime.users.base import PerfBaseUser


class OutboundUser(PerfBaseUser):
    weight = 1
    workload_name = "outbound"
    flow_class = "outbound"

    @task
    def prompt(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        flow = self.require_flow("perf_outbound_basic_prompting")
        workflows = self.workflows_client()
        if flow is None or workflows is None:
            return
        workflows.run_sync(
            flow_id=str(flow["flow_id"]),
            input_value=DEFAULT_OUTBOUND_PROMPT,
            session_id=self.session_id,
        )
