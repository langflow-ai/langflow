from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from langflow.api.v1 import endpoints, openai_responses
from langflow.schema import OpenAIResponsesRequest
from langflow.services.telemetry import run_event_store
from langflow.services.telemetry.service import TelemetryService


@pytest.fixture(params=["enabled", "opted_out", "keyless"])
def telemetry_service(request, monkeypatch, tmp_path):
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    settings = SimpleNamespace(
        segment_api_url="https://api.segment.test/v1/track",
        segment_write_key="segment-test-key" if request.param != "keyless" else "",
        do_not_track=request.param == "opted_out",
        config_dir=str(tmp_path),
        prometheus_enabled=False,
        edition="opensource",
    )
    service = TelemetryService(SimpleNamespace(settings=settings))
    run_event_store.pop_all()
    yield service
    run_event_store.pop_all()


def _assert_recorded_run(telemetry_service, *, success, completed_at):
    events = run_event_store.pop_all()
    assert len(events) == 1
    event = events[0]
    assert event.run_success is success
    assert event.run_completed_at == completed_at
    if telemetry_service.do_not_track or not telemetry_service.segment_write_key:
        assert telemetry_service.telemetry_queue.empty()
    else:
        assert telemetry_service.telemetry_queue.qsize() == 1
        _, queued_payload, path, _ = telemetry_service.telemetry_queue.get_nowait()
        telemetry_service.telemetry_queue.task_done()
        assert queued_payload is event
        assert path == "run"
    # Completion timestamps belong to local metering, not outbound analytics.
    assert "run_completed_at" not in event.model_dump()


@pytest.mark.parametrize("failure_type", [None, ValueError, RuntimeError])
async def test_served_v1_run_records_success_and_failure(monkeypatch, telemetry_service, failure_type):
    completed_at = datetime(2026, 10, 28, 23, 59, 59, tzinfo=timezone.utc)

    class CompletionClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return completed_at if tz is None else completed_at.astimezone(tz)

    flow = SimpleNamespace(id=uuid4(), user_id=uuid4(), workspace_id=None, folder_id=None, data=None)
    user = SimpleNamespace(id=flow.user_id)
    run = AsyncMock(return_value=object())
    if failure_type:
        run.side_effect = failure_type("flow run failed")
    monkeypatch.setattr(run_event_store, "datetime", CompletionClock)
    monkeypatch.setattr(endpoints, "get_telemetry_service", lambda: telemetry_service)
    monkeypatch.setattr(endpoints, "resolve_serving_scope", lambda **_: None)
    monkeypatch.setattr(endpoints, "simple_run_flow", run)
    monkeypatch.setattr(endpoints, "_v1_run_response", lambda _: JSONResponse({"status": "ok"}))
    monkeypatch.setattr(endpoints, "ensure_flow_permission", AsyncMock())
    app = FastAPI()
    app.include_router(endpoints.router, prefix="/api/v1")
    app.dependency_overrides[endpoints.get_flow_for_api_key_user] = lambda: flow
    app.dependency_overrides[endpoints.api_key_security] = lambda: user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/run/{flow.id}", json={})

    assert response.status_code == (500 if failure_type else 200)
    if failure_type:
        assert "flow run failed" in response.text
    else:
        assert response.json() == {"status": "ok"}
    run.assert_awaited_once()
    _assert_recorded_run(telemetry_service, success=failure_type is None, completed_at=completed_at)


@pytest.mark.parametrize("failure_type", [None, RuntimeError])
async def test_openai_completion_keeps_run_day_when_recording_is_deferred(monkeypatch, telemetry_service, failure_type):
    completed_at = datetime(2026, 10, 28, 23, 59, 59, tzinfo=timezone.utc)
    recorded_at = datetime(2026, 10, 29, 0, 0, 1, tzinfo=timezone.utc)

    class CompletionClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return completed_at if tz is None else completed_at.astimezone(tz)

    class RecordingClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return recorded_at if tz is None else recorded_at.astimezone(tz)

    flow = SimpleNamespace(id=uuid4(), user_id=uuid4(), workspace_id=None, folder_id=None, data=None)
    result = object()
    run = AsyncMock(return_value=result)
    if failure_type:
        run.side_effect = failure_type("flow run failed")
    monkeypatch.setattr(openai_responses, "datetime", CompletionClock)
    monkeypatch.setattr(run_event_store, "datetime", RecordingClock)
    monkeypatch.setattr(openai_responses, "get_flow_by_id_or_endpoint_name", AsyncMock(return_value=flow))
    monkeypatch.setattr(openai_responses, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(openai_responses, "resolve_serving_scope", lambda **_: None)
    monkeypatch.setattr(openai_responses, "run_flow_for_openai_responses", run)
    background_tasks = BackgroundTasks()

    response = await openai_responses.create_response(
        request=OpenAIResponsesRequest(model=str(flow.id), input="hello"),
        background_tasks=background_tasks,
        api_key_user=SimpleNamespace(id=flow.user_id),
        telemetry_service=telemetry_service,
        http_request=Request({"type": "http", "headers": []}),
    )

    if failure_type:
        assert response.error["type"] == "processing_error"
        assert "flow run failed" in response.error["message"]
    else:
        assert response is result
    run.assert_awaited_once()
    assert run_event_store.peek_all() == []
    await background_tasks()
    _assert_recorded_run(telemetry_service, success=failure_type is None, completed_at=completed_at)
