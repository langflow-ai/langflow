"""Unit tests for drain-phase helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from tests.locust.langflow_runtime.clients.base import ApiClient, HttpxTransport, LocustTransport
from tests.locust.langflow_runtime.metrics.registry import TrackedWorkflowJob, get_registry
from tests.locust.langflow_runtime.shapes.drain import drain_remaining_s, drain_tracked_work, reset_movement_state


def test_drain_remaining_s() -> None:
    assert drain_remaining_s(10.0, 30.0) == 20.0
    assert drain_remaining_s(30.0, 30.0) == 0.0
    assert drain_remaining_s(45.0, 30.0) == 0.0


def test_reset_movement_state_clears_registry() -> None:
    registry = get_registry()
    registry.clear_all()
    registry.register_workflow(TrackedWorkflowJob(job_id="job-1", flow_id="flow-1", accepted_at=datetime.now(UTC)))
    assert len(registry.list_workflows()) == 1

    environment = SimpleNamespace(webhook_pool=None, stop_new_arrivals=True, perf_drain_started=True)
    reset_movement_state(environment)

    assert registry.list_workflows() == []
    assert environment.stop_new_arrivals is False
    assert environment.perf_drain_started is False


def test_httpx_and_locust_transports_are_distinct() -> None:
    import httpx

    assert isinstance(ApiClient.from_httpx(httpx.Client(), base_url="http://example.test").transport, HttpxTransport)
    assert isinstance(ApiClient.from_locust(object(), base_url="http://example.test").transport, LocustTransport)


def test_drain_tracked_work_advances_workflow_terminal() -> None:
    registry = get_registry()
    registry.clear_all()
    registry.register_workflow(
        TrackedWorkflowJob(
            job_id="job-drain",
            flow_id="flow-1",
            accepted_at=datetime.now(UTC),
            status="pending",
        )
    )

    class FakeStatus:
        terminal = True
        success = True
        status = "completed"

    class FakeWorkflows:
        def get_status(self, job_id: str) -> FakeStatus:
            assert job_id == "job-drain"
            return FakeStatus()

    environment = SimpleNamespace(run_context=None, host="http://localhost:7860")
    import tests.locust.langflow_runtime.shapes.drain as drain_mod

    original = drain_mod._workflows_client_from_environment
    drain_mod._workflows_client_from_environment = lambda _env: FakeWorkflows()  # type: ignore[assignment]
    try:
        report = drain_tracked_work(environment, deadline_s=2.0)
    finally:
        drain_mod._workflows_client_from_environment = original

    assert report["outstanding_workflow_count"] == 0
    jobs = registry.list_workflows()
    assert len(jobs) == 1
    assert jobs[0].status == "completed"
    assert jobs[0].success is True


def test_locust_transport_named_request_skips_catch_response_on_plain_session() -> None:
    class FakeResp:
        status_code = 200
        text = '{"ok": true}'
        headers = {"content-type": "application/json"}

    class FakeSession:
        def get(self, url: str, **kwargs):  # noqa: ARG002
            assert "catch_response" not in kwargs
            return FakeResp()

    client = ApiClient.from_locust(FakeSession(), base_url="http://example.test", api_key="k")
    response = client.request("GET", "/health", name="health:get:test:passthrough")
    assert response.status_code == 200


def test_httpx_transport_uses_send_stream() -> None:
    class FakeResp:
        status_code = 200
        text = "ok"
        headers = {}

        def iter_lines(self):
            return iter(())

        def close(self) -> None:
            return None

    class FakeHttpx:
        def __init__(self) -> None:
            self.sent_stream: bool | None = None

        def build_request(self, method: str, url: str, **kwargs):  # noqa: ARG002
            return {"method": method, "url": url}

        def send(self, request, *, stream: bool = False):  # noqa: ARG002
            self.sent_stream = stream
            return FakeResp()

    fake = FakeHttpx()
    client = ApiClient.from_httpx(fake, base_url="http://example.test", api_key="k")
    response = client.request("GET", "/events", stream=True)
    assert response.status_code == 200
    assert fake.sent_stream is True
