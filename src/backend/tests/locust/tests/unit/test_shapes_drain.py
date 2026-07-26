"""Unit tests for drain-phase helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from tests.locust.langflow_runtime.clients.base import ApiClient, _supports_locust_catch_response
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


def test_httpx_client_does_not_use_catch_response() -> None:
    import httpx

    assert _supports_locust_catch_response(httpx.Client()) is False


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


def test_api_client_named_request_with_httpx_does_not_raise() -> None:
    import httpx

    class FakeResp:
        status_code = 200
        text = '{"ok": true}'
        headers = {"content-type": "application/json"}

    class FakeHttp:
        def get(self, url: str, **kwargs):  # noqa: ARG002
            assert "catch_response" not in kwargs
            return FakeResp()

        def request(self, method: str, url: str, **kwargs):  # noqa: ARG002
            assert "catch_response" not in kwargs
            return FakeResp()

    # Pretend to be httpx by setting module attribute on the class.
    FakeHttp.__module__ = "httpx"
    client = ApiClient(FakeHttp(), base_url="http://example.test", api_key="k")
    response = client.request("GET", "/health", name="health:get:test:passthrough")
    assert response.status_code == 200
