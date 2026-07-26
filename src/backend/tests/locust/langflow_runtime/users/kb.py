"""Knowledge-base Locust users."""

from __future__ import annotations

from locust import task

from tests.locust.langflow_runtime.flows.defaults import DEFAULT_KB_DOC_PREFIX, DEFAULT_KB_QUERY
from tests.locust.langflow_runtime.metrics.correctness import expect_kb_retrieval
from tests.locust.langflow_runtime.users.base import PerfBaseUser, extract_output_text


class KbIngestUser(PerfBaseUser):
    weight = 1
    workload_name = "kb_ingest"
    flow_class = "kb_ingest"

    @task
    def ingest(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        flow = self.require_flow("perf_kb_ingest")
        workflows = self.workflows_client()
        if flow is None or workflows is None:
            return
        workflows.run_sync(
            flow_id=str(flow["flow_id"]),
            input_value=DEFAULT_KB_DOC_PREFIX,
            session_id=self.session_id,
        )


class KbRetrieveUser(PerfBaseUser):
    weight = 1
    workload_name = "kb_retrieve"
    flow_class = "kb_retrieve"

    @task
    def retrieve(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        flow = self.require_flow("perf_kb_retrieve")
        workflows = self.workflows_client()
        if flow is None or workflows is None:
            return
        result = workflows.run_sync(
            flow_id=str(flow["flow_id"]),
            input_value=DEFAULT_KB_QUERY,
            session_id=self.session_id,
        )
        text = extract_output_text(result)
        check = expect_kb_retrieval(text, DEFAULT_KB_QUERY)
        if text and not check.ok:
            raise AssertionError(check.reason or "kb retrieval marker missing")
