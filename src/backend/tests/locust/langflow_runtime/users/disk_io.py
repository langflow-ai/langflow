"""Disk I/O Locust user."""

from __future__ import annotations

from locust import task

from tests.locust.langflow_runtime.metrics.correctness import expect_disk_io_contract
from tests.locust.langflow_runtime.users.base import PerfBaseUser, extract_output_text, parse_kv_metrics


class DiskIoUser(PerfBaseUser):
    weight = 1
    workload_name = "disk_io"
    flow_class = "disk_io"

    @task
    def disk_io(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        flow = self.require_flow_or_fail("perf_disk_io")
        workflows = self.require_workflows_client()
        result = workflows.run_sync(
            flow_id=str(flow["flow_id"]),
            input_value="perf-disk",
            session_id=self.session_id,
        )
        text = extract_output_text(result)
        parsed = parse_kv_metrics(text, prefix="diskio")
        if parsed is None:
            raise AssertionError(f"disk I/O output missing metrics header: {text!r}")
        check = expect_disk_io_contract(parsed)
        if not check.ok:
            raise AssertionError(check.reason or "disk I/O contract failed")
