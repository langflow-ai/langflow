"""Queue Locust user — background submit vs observe."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import gevent
from locust import task

from tests.locust.langflow_runtime.flows.defaults import DEFAULT_QUEUE_INPUT
from tests.locust.langflow_runtime.metrics.registry import TrackedWorkflowJob
from tests.locust.langflow_runtime.users.base import (
    PerfBaseUser,
    get_or_create_arrival_accountant,
    get_or_create_paced_arrival_scheduler,
)


class QueueUser(PerfBaseUser):
    weight = 1
    workload_name = "queue"
    flow_class = "queue_short"

    def on_start(self) -> None:
        super().on_start()
        self._observe_cursor = 0
        self._arrival_scheduler = None
        if self.run_context is not None:
            workload = self.run_context.profile.workload
            rate = workload.axis_arrival_rates.get("queue") or workload.arrival_rate_per_s
            if rate is None:
                msg = "QueueUser requires workload arrival pacing (queue axis_arrival_rates or arrival_rate_per_s)"
                raise RuntimeError(msg)
            self._arrival_scheduler = get_or_create_paced_arrival_scheduler(
                self.environment,
                rate_per_s=float(rate),
                allowed_lateness_s=float(self.run_context.profile.validity.allowed_scheduling_lateness_s),
            )

    def _paced(self) -> bool:
        return self._arrival_scheduler is not None

    @task(3)
    def submit_background(self) -> None:
        if self.run_context is None:
            return
        accountant = get_or_create_arrival_accountant(self.environment) if self._paced() else None
        if accountant is not None:
            reservation = self._arrival_scheduler.reserve()
            accountant.record_intended_slot(reservation.missed_slots + 1)
            if reservation.missed_slots:
                accountant.record_miss("scheduling_late", reservation.missed_slots)
            if reservation.delay_s:
                gevent.sleep(reservation.delay_s)
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
