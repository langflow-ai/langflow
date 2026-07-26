"""Queue Locust user — background submit vs observe."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from locust import task

from tests.locust.langflow_runtime.flows.defaults import DEFAULT_QUEUE_INPUT
from tests.locust.langflow_runtime.metrics.registry import TrackedWorkflowJob
from tests.locust.langflow_runtime.users.base import PerfBaseUser, get_or_create_arrival_accountant


class QueueUser(PerfBaseUser):
    weight = 1
    workload_name = "queue"
    flow_class = "queue_short"

    def on_start(self) -> None:
        super().on_start()
        self._observe_cursor = 0

    def _paced(self) -> bool:
        return bool(self.run_context is not None and self.run_context.profile.workload.workload_model == "paced_closed")

    @task(3)
    def submit_background(self) -> None:
        if self.run_context is None:
            return
        accountant = get_or_create_arrival_accountant(self.environment) if self._paced() else None
        if accountant is not None:
            accountant.record_intended_slot()
        if self.stop_new_arrivals():
            if accountant is not None:
                accountant.record_miss("stop_new_arrivals")
            return

        flow = self.require_flow_or_fail("perf_queue_short")
        workflows = self.require_workflows_client()

        if accountant is not None:
            accountant.record_attempt()
        try:
            job_id = workflows.submit_background(
                flow_id=str(flow["flow_id"]),
                input_value=DEFAULT_QUEUE_INPUT,
                session_id=f"{self.session_id}-{uuid.uuid4().hex[:8]}",
            )
        except Exception:
            if accountant is not None:
                accountant.record_miss("submit_failed")
            raise

        self.registry.register_workflow(
            TrackedWorkflowJob(
                job_id=job_id,
                flow_id=str(flow["flow_id"]),
                accepted_at=datetime.now(UTC),
                status="pending",
            )
        )
        if accountant is not None:
            accountant.record_accepted()

    @task(2)
    def observe_terminal(self) -> None:
        if self.run_context is None:
            return
        workflows = self.require_workflows_client()
        outstanding = self.registry.outstanding_workflows()
        if not outstanding:
            return
        # Round-robin so later jobs are not starved behind outstanding[0].
        idx = self._observe_cursor % len(outstanding)
        self._observe_cursor += 1
        job = outstanding[idx]
        status = workflows.get_status(job.job_id)
        if not status.terminal:
            return
        self.registry.update_workflow(
            job.job_id,
            status=status.status,
            success=status.success,
            terminal_at=datetime.now(UTC),
        )
        if self._paced():
            accountant = get_or_create_arrival_accountant(self.environment)
            accountant.record_terminal(success=bool(status.success))
