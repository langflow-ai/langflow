from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException, Request
from langflow.api.v1 import endpoints
from langflow.exceptions.api import APIException
from langflow.services.telemetry import run_event_store
from langflow.services.telemetry.service import TelemetryService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected_success"),
    [
        (None, True),
        (ValueError("component failed"), False),
        (RuntimeError("unexpected failure"), False),
    ],
)
async def test_background_telemetry_keeps_terminal_completion_day_after_delay(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception | None,
    *,
    expected_success: bool,
) -> None:
    completed_at = datetime(2026, 9, 14, 23, 59, 59, tzinfo=timezone.utc)
    delayed_at = datetime(2026, 9, 15, 0, 0, 1, tzinfo=timezone.utc)

    class CompletionClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return completed_at if tz is None else completed_at.astimezone(tz)

    class DelayedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return delayed_at if tz is None else delayed_at.astimezone(tz)

    flow = SimpleNamespace(id=uuid4(), user_id=uuid4(), workspace_id=None, folder_id=None, data=None)
    user = SimpleNamespace(id=flow.user_id)
    input_request = SimpleNamespace(session_id=None, tweaks=None)
    telemetry_service = TelemetryService(SimpleNamespace(settings=SimpleNamespace(prometheus_enabled=False)))
    background_tasks = BackgroundTasks()
    response = object()

    monkeypatch.setattr(endpoints, "datetime", CompletionClock)
    monkeypatch.setattr(endpoints, "get_telemetry_service", lambda: telemetry_service)
    monkeypatch.setattr(endpoints, "resolve_serving_scope", lambda **_: None)
    run = AsyncMock(return_value=object()) if failure is None else AsyncMock(side_effect=failure)
    monkeypatch.setattr(endpoints, "simple_run_flow", run)
    monkeypatch.setattr(endpoints, "_v1_run_response", lambda _: response)

    run_event_store.pop_all()
    try:
        if failure is None:
            result = await endpoints._run_flow_internal(
                background_tasks=background_tasks,
                flow=flow,
                input_request=input_request,
                stream=False,
                api_key_user=user,
                context=None,
                http_request=Request({"type": "http", "headers": []}),
            )
            assert result is response
        else:
            with pytest.raises(HTTPException) as exc_info:
                await endpoints._run_flow_internal(
                    background_tasks=background_tasks,
                    flow=flow,
                    input_request=input_request,
                    stream=False,
                    api_key_user=user,
                    context=None,
                    http_request=Request({"type": "http", "headers": []}),
                )
            assert isinstance(exc_info.value, APIException)
            assert exc_info.value.status_code == 500
            assert str(failure) in str(exc_info.value.detail)

        assert len(background_tasks.tasks) == 1

        monkeypatch.setattr(run_event_store, "datetime", DelayedClock)
        await background_tasks()

        events = run_event_store.pop_all()
        assert len(events) == 1
        assert events[0].run_success is expected_success
        assert events[0].run_completed_at == completed_at
    finally:
        run_event_store.pop_all()
        await telemetry_service.teardown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected_success"),
    [(None, True), (RuntimeError("component failed"), False)],
)
async def test_simple_run_flow_task_records_terminal_timestamp_for_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception | None,
    *,
    expected_success: bool,
) -> None:
    completed_at = datetime(2026, 9, 14, 23, 59, 59, tzinfo=timezone.utc)

    class CompletionClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return completed_at if tz is None else completed_at.astimezone(tz)

    flow = SimpleNamespace(id=uuid4(), user_id=uuid4(), workspace_id=None, folder_id=None, data={"nodes": []})
    telemetry_service = TelemetryService(SimpleNamespace(settings=SimpleNamespace(prometheus_enabled=False)))
    run = AsyncMock(return_value=object()) if failure is None else AsyncMock(side_effect=failure)
    monkeypatch.setattr(endpoints, "datetime", CompletionClock)
    monkeypatch.setattr(endpoints, "simple_run_flow", run)
    run_event_store.pop_all()

    try:
        result = await endpoints.simple_run_flow_task(
            flow=flow,
            input_request=SimpleNamespace(input_value="", tweaks=None),
            api_key_user=SimpleNamespace(id=flow.user_id),
            telemetry_service=telemetry_service,
            start_time=0.0,
            run_id="run-task",
        )

        assert (result is not None) is expected_success
        events = run_event_store.pop_all()
        assert len(events) == 1
        assert events[0].run_is_webhook is True
        assert events[0].run_success is expected_success
        assert events[0].run_completed_at == completed_at
    finally:
        run_event_store.pop_all()
        await telemetry_service.teardown()
