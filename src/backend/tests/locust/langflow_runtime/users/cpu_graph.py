"""CPU graph Locust user."""

from __future__ import annotations

from locust import task

from tests.locust.langflow_runtime.users.base import PerfBaseUser


class CpuGraphUser(PerfBaseUser):
    weight = 1
    workload_name = "cpu_graph"
    flow_class = "cpu_graph"

    @task
    def burn(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        flow = self.require_flow("perf_cpu_graph")
        workflows = self.workflows_client()
        if flow is None or workflows is None:
            return
        workflows.run_sync(
            flow_id=str(flow["flow_id"]),
            input_value="perf-cpu-graph",
            session_id=self.session_id,
        )
