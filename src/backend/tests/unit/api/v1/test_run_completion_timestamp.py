from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, Request
from langflow.api.v1 import endpoints
from langflow.services.telemetry import run_event_store
from langflow.services.telemetry.service import TelemetryService


@pytest.mark.asyncio
async def test_background_telemetry_keeps_terminal_completion_day_after_delay(
    monkeypatch: pytest.MonkeyPatch,
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

    flow = SimpleNamespace(id=uuid4(), user_id=uuid4(), workspace_id=None, folder_id=None)
    user = SimpleNamespace(id=flow.user_id)
    input_request = SimpleNamespace(session_id=None, tweaks=None)
    telemetry_service = TelemetryService(SimpleNamespace(settings=SimpleNamespace(prometheus_enabled=False)))
    background_tasks = BackgroundTasks()
    response = object()

    monkeypatch.setattr(endpoints, "datetime", CompletionClock)
    monkeypatch.setattr(endpoints, "get_telemetry_service", lambda: telemetry_service)
    monkeypatch.setattr(endpoints, "resolve_serving_scope", lambda **_: None)
    monkeypatch.setattr(endpoints, "simple_run_flow", AsyncMock(return_value=object()))
    monkeypatch.setattr(endpoints, "_v1_run_response", lambda _: response)

    run_event_store.pop_all()
    try:
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
        assert len(background_tasks.tasks) == 1

        monkeypatch.setattr(run_event_store, "datetime", DelayedClock)
        await background_tasks()

        events = run_event_store.pop_all()
        assert len(events) == 1
        assert events[0].run_completed_at == completed_at
    finally:
        run_event_store.pop_all()
        await telemetry_service.teardown()
