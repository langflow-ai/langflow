"""Ensemble flow Locust user."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from locust import task

from tests.locust.langflow_runtime.config.naming import metric_name
from tests.locust.langflow_runtime.contracts import DEFAULT_WEBHOOK_PAYLOAD
from tests.locust.langflow_runtime.metrics.lifecycle import lifecycle_timer
from tests.locust.langflow_runtime.metrics.registry import TrackedHitlRequest, TrackedWorkflowJob
from tests.locust.langflow_runtime.users.base import PerfBaseUser, get_or_create_webhook_pool

_DEFAULT_DECISION = {"action_id": "approve"}


class EnsembleFlowUser(PerfBaseUser):
    weight = 1
    workload_name = "ensemble_flow"
    flow_class = "ensemble"

    def _selectors(self) -> list[str]:
        if self.run_context is None:
            return []
        return list(self.run_context.profile.flow_selectors)

    def _use_hitl(self) -> bool:
        return "perf_ensemble_journey_hitl" in self._selectors()

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
    def journey(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return

        if self._use_hitl():
            self._run_hitl_journey()
            return

        flow = self.require_flow("perf_ensemble_journey")
        workflows = self.workflows_client()
        if flow is None or workflows is None:
            return

        flow_id = str(flow["flow_id"])
        session_id = f"{self.session_id}-{uuid.uuid4().hex[:8]}"
        name = metric_name("workflows", "ensemble_sync", self.workload_name, self.flow_class)
        with lifecycle_timer(name):
            workflows.run_sync(flow_id=flow_id, input_value="perf-ensemble", session_id=session_id)

        protocols = self.run_context.profile.protocols if self.run_context else []

        # Prefer the ensemble journey for MCP when provisioned; fall back to passthrough.
        mcp_flow = self.require_flow("perf_ensemble_journey") or self.require_flow("perf_passthrough")
        mcp = self.mcp_client(
            workload="ensemble_flow",
            flow_class="ensemble"
            if mcp_flow and mcp_flow.get("fixture_id") == "perf_ensemble_journey"
            else "passthrough",
        )
        if mcp_flow is not None and mcp is not None and "mcp" in protocols:
            tool_name = str(mcp_flow.get("mcp_action_name") or mcp_flow.get("fixture_id") or "perf_passthrough")
            mcp_name = metric_name("mcp", "ensemble_call", self.workload_name, "ensemble")
            with lifecycle_timer(mcp_name):
                mcp.full_lifecycle_call(tool_name, {"input_value": "perf-ensemble"})

        # Optional webhook path when copies are provisioned.
        if "webhook" in protocols:
            webhooks = self.webhooks_client(workload="ensemble_flow", flow_class="passthrough")
            pool = get_or_create_webhook_pool(self.environment, self.provision_state)
            if webhooks is not None and pool is not None:
                copy = pool.lease(timeout_s=5.0)
                try:
                    wh_name = metric_name("webhook", "ensemble_lifecycle", self.workload_name, "passthrough")
                    with lifecycle_timer(wh_name):
                        result = webhooks.subscribe_post_complete(
                            copy, dict(DEFAULT_WEBHOOK_PAYLOAD), timeout_s=self.deadline_s()
                        )
                    if result.error:
                        raise RuntimeError(result.error)
                finally:
                    pool.release(copy)

    def _run_hitl_journey(self) -> None:
        flow = self.require_flow("perf_ensemble_journey_hitl")
        workflows = self.workflows_client(workload="ensemble_flow_hitl", flow_class="ensemble_hitl")
        if flow is None or workflows is None:
            return

        flow_id = str(flow["flow_id"])
        session_id = f"{self.session_id}-{uuid.uuid4().hex[:8]}"
        name = metric_name("workflows", "ensemble_hitl", self.workload_name, "ensemble_hitl")
        with lifecycle_timer(name):
            job_id = workflows.submit_background(
                flow_id=flow_id,
                input_value="perf-ensemble-hitl",
                session_id=session_id,
            )
            self.registry.register_workflow(
                TrackedWorkflowJob(job_id=job_id, flow_id=flow_id, accepted_at=datetime.now(UTC), status="pending")
            )
            self._wait_for_status(workflows, job_id, want={"suspended"})
            pending = workflows.pending_for_job(flow_id, job_id)
            if pending is None:
                raise RuntimeError(f"no pending HITL row for ensemble job {job_id}")
            request_id = str(pending.get("request_id") or "")
            self.registry.register_hitl(
                TrackedHitlRequest(job_id=job_id, request_id=request_id, flow_id=flow_id, phase="pending")
            )
            workflows.resume(job_id, request_id=request_id, decision=_DEFAULT_DECISION)
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
                raise RuntimeError(f"ensemble HITL failed: {final.status}")
