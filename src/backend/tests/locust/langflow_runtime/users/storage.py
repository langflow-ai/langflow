"""RAM/storage Locust user."""

from __future__ import annotations

from locust import task

from tests.locust.langflow_runtime.datasets.storage_payload import bounded_payload_text
from tests.locust.langflow_runtime.users.base import PerfBaseUser


class StorageUser(PerfBaseUser):
    weight = 1
    workload_name = "ram_storage"
    flow_class = "payload_echo"

    @task
    def store_payload(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        flow = self.require_flow("perf_payload_echo")
        workflows = self.workflows_client()
        if flow is None or workflows is None:
            return
        workflows.run_sync(
            flow_id=str(flow["flow_id"]),
            input_value=bounded_payload_text(),
            session_id=self.session_id,
        )
