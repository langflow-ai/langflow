"""Protocol calibration Locust user."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime

from locust import task

from tests.locust.langflow_runtime.config.naming import metric_name
from tests.locust.langflow_runtime.flows.defaults import DEFAULT_PASSTHROUGH_INPUT
from tests.locust.langflow_runtime.metrics.lifecycle import lifecycle_timer
from tests.locust.langflow_runtime.metrics.registry import TrackedMcpCall, TrackedWorkflowJob
from tests.locust.langflow_runtime.users.base import PerfBaseUser

_CALIBRATION_PROTOCOLS = (
    "mcp",
    "workflows_sync",
    "workflows_stream",
    "workflows_background",
)


class ProtocolCalibrationUser(PerfBaseUser):
    weight = 1
    workload_name = "protocol_calibration"
    flow_class = "passthrough"

    def on_start(self) -> None:
        super().on_start()
        self._protocol_cycle = 0
        protocols = []
        if self.run_context is not None:
            protocols = [p for p in self.run_context.profile.protocols if p in _CALIBRATION_PROTOCOLS]
        self._protocols = protocols or list(_CALIBRATION_PROTOCOLS)

    def _next_protocol(self) -> str:
        if not self._protocols:
            return "workflows_sync"
        protocol = self._protocols[self._protocol_cycle % len(self._protocols)]
        self._protocol_cycle += 1
        # Occasionally shuffle to avoid lock-step across users.
        if self._protocol_cycle % 7 == 0:
            random.shuffle(self._protocols)
        return protocol

    @task
    def calibrate(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        flow = self.require_flow("perf_passthrough")
        if flow is None:
            return

        protocol = self._next_protocol()
        flow_id = str(flow["flow_id"])
        session_id = f"{self.session_id}-{uuid.uuid4().hex[:8]}"

        if protocol == "mcp":
            client = self.mcp_client()
            if client is None:
                return
            tool_name = str(flow.get("mcp_action_name") or "perf_passthrough")
            name = metric_name("mcp", "full_lifecycle", self.workload_name, self.flow_class)
            with lifecycle_timer(name):
                started = datetime.now(UTC)
                result = client.full_lifecycle_call(tool_name, {"input_value": DEFAULT_PASSTHROUGH_INPUT})
                self.registry.register_mcp(
                    TrackedMcpCall(tool_name=tool_name, started_at=started, finished_at=datetime.now(UTC), success=True)
                )
                _ = result
            return

        workflows = self.workflows_client()
        if workflows is None:
            return

        if protocol == "workflows_sync":
            name = metric_name("workflows", "sync_lifecycle", self.workload_name, self.flow_class)
            with lifecycle_timer(name):
                workflows.run_sync(flow_id=flow_id, input_value=DEFAULT_PASSTHROUGH_INPUT, session_id=session_id)
            return

        if protocol == "workflows_stream":
            name = metric_name("workflows", "stream_lifecycle", self.workload_name, self.flow_class)
            with lifecycle_timer(name):
                workflows.run_stream(flow_id=flow_id, input_value=DEFAULT_PASSTHROUGH_INPUT, session_id=session_id)
            return

        if protocol == "workflows_background":
            name = metric_name("workflows", "background_lifecycle", self.workload_name, self.flow_class)
            with lifecycle_timer(name):
                job_id = workflows.submit_background(
                    flow_id=flow_id,
                    input_value=DEFAULT_PASSTHROUGH_INPUT,
                    session_id=session_id,
                )
                self.registry.register_workflow(
                    TrackedWorkflowJob(job_id=job_id, flow_id=flow_id, accepted_at=datetime.now(UTC), status="pending")
                )
                status = workflows.wait_until_terminal(
                    job_id,
                    poll_interval_s=self.poll_interval_s(),
                    deadline_s=self.deadline_s(),
                )
                self.registry.update_workflow(
                    job_id,
                    status=status.status,
                    success=status.success,
                    terminal_at=datetime.now(UTC),
                )
