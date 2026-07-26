"""HITL Locust user."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from locust import task

from tests.locust.langflow_runtime.config.naming import metric_name
from tests.locust.langflow_runtime.metrics.lifecycle import lifecycle_timer
from tests.locust.langflow_runtime.metrics.registry import TrackedHitlRequest, TrackedWorkflowJob
from tests.locust.langflow_runtime.users.base import PerfBaseUser

_DEFAULT_DECISION = {"action_id": "approve"}


class HitlUser(PerfBaseUser):
    weight = 1
    workload_name = "hitl"
    flow_class = "human_input"

    def _wait_for_status(self, workflows, job_id: str, *, want: set[str]):
        started = time.monotonic()
        while True:
            status = workflows.get_status(job_id)
            if status.status in want:
                return status
            if time.monotonic() - started >= self.deadline_s():
                msg = f"job {job_id} did not reach {sorted(want)} (last={status.status})"
                raise RuntimeError(msg)
            time.sleep(self.poll_interval_s())

    @task
    def hitl_cycle(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        flow = self.require_flow("human_input_flow")
        workflows = self.workflows_client()
        if flow is None or workflows is None:
            return

        flow_id = str(flow["flow_id"])
        session_id = f"{self.session_id}-{uuid.uuid4().hex[:8]}"
        name = metric_name("workflows", "hitl_lifecycle", self.workload_name, self.flow_class)
        with lifecycle_timer(name):
            job_id = workflows.submit_background(
                flow_id=flow_id,
                input_value="Approve this?",
                session_id=session_id,
            )
            self.registry.register_workflow(
                TrackedWorkflowJob(job_id=job_id, flow_id=flow_id, accepted_at=datetime.now(UTC), status="pending")
            )
            self._wait_for_status(workflows, job_id, want={"suspended"})
            pending = workflows.pending_for_job(flow_id, job_id)
            if pending is None:
                raise RuntimeError(f"no pending HITL row for job {job_id}")
            request_id = str(pending.get("request_id") or "")
            if not request_id:
                raise RuntimeError("pending HITL row missing request_id")
            self.registry.register_hitl(
                TrackedHitlRequest(job_id=job_id, request_id=request_id, flow_id=flow_id, phase="pending")
            )
            workflows.resume(job_id, request_id=request_id, decision=_DEFAULT_DECISION)
            self.registry.update_hitl(request_id, phase="resuming")
            final = workflows.wait_until_terminal(
                job_id,
                poll_interval_s=self.poll_interval_s(),
                deadline_s=self.deadline_s(),
            )
            self.registry.update_workflow(
                job_id,
                status=final.status,
                success=final.success,
                terminal_at=datetime.now(UTC),
            )
            self.registry.update_hitl(request_id, phase="completed" if final.success else final.status)
            if not final.success:
                raise RuntimeError(f"HITL lifecycle failed: {final.status}")
