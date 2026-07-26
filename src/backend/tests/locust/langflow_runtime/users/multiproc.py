"""Multiprocess churn Locust user."""

from __future__ import annotations

from locust import task

from tests.locust.langflow_runtime.metrics.correctness import expect_multiproc_metrics
from tests.locust.langflow_runtime.users.base import PerfBaseUser, extract_output_text, parse_multiproc_header


class MultiprocUser(PerfBaseUser):
    weight = 1
    workload_name = "multiproc"
    flow_class = "multiproc"

    @task
    def churn(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        flow = self.require_flow_or_fail("perf_multiproc_churn")
        workflows = self.require_workflows_client()
        result = workflows.run_sync(
            flow_id=str(flow["flow_id"]),
            input_value="perf-multiproc",
            session_id=self.session_id,
        )
        text = extract_output_text(result)
        parsed = parse_multiproc_header(text)
        if parsed is None:
            raise AssertionError(f"multiproc output missing metrics header: {text!r}")
        check = expect_multiproc_metrics(parsed)
        if not check.ok:
            raise AssertionError(check.reason or "multiproc metrics invalid")
