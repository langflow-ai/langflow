from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException, Request
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.events.event_manager import create_stream_tokens_event_manager


def _request() -> Request:
    return Request({"type": "http", "headers": []})


def _flow(*, owner_id, data: dict | None = None):
    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        workspace_id=None,
        folder_id=None,
        name="shared-flow",
        data=data or {"nodes": [], "edges": []},
    )


@pytest.mark.parametrize("stream", [False, True])
async def test_v1_run_non_owner_tweaks_are_hidden_as_not_found(
    monkeypatch: pytest.MonkeyPatch,
    stream: bool,  # noqa: FBT001
) -> None:
    from langflow.api.v1 import endpoints

    owner_id = uuid4()
    caller = SimpleNamespace(id=uuid4(), is_superuser=False)

    async def execution_must_not_start(**_kwargs):
        message = "delegated tweaks must be rejected before execution"
        raise AssertionError(message)

    async def stream_execution_must_not_start(**kwargs):
        await kwargs["event_manager"].queue.put((None, None, 0.0))

    monkeypatch.setattr(
        endpoints,
        "get_telemetry_service",
        lambda: SimpleNamespace(log_package_run=AsyncMock()),
    )
    monkeypatch.setattr(endpoints, "simple_run_flow", execution_must_not_start)
    monkeypatch.setattr(endpoints, "run_flow_generator", stream_execution_must_not_start)

    with pytest.raises(HTTPException) as exc_info:
        await endpoints._run_flow_internal(
            background_tasks=BackgroundTasks(),
            flow=_flow(owner_id=owner_id),
            input_request=SimplifiedAPIRequest(
                input_value="hello",
                input_type="chat",
                output_type="chat",
                tweaks={"ChatInput-1": {"input_value": "owner-only override"}},
            ),
            stream=stream,
            api_key_user=caller,
            context=None,
            http_request=_request(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Flow not found"


@pytest.mark.parametrize("expose_error_details", [False, True])
async def test_v1_run_stream_error_depends_on_flow_ownership(
    monkeypatch: pytest.MonkeyPatch,
    expose_error_details: bool,  # noqa: FBT001
) -> None:
    from langflow.api.v1 import endpoints

    sensitive_detail = "owner-provider-secret"

    async def fail_run(**_kwargs):
        raise RuntimeError(sensitive_detail)

    monkeypatch.setattr(endpoints, "simple_run_flow", fail_run)
    queue: asyncio.Queue = asyncio.Queue()
    consumed: asyncio.Queue = asyncio.Queue()
    event_manager = create_stream_tokens_event_manager(queue)

    await endpoints.run_flow_generator(
        flow=_flow(owner_id=uuid4()),
        input_request=SimplifiedAPIRequest(input_value="hello"),
        api_key_user=SimpleNamespace(id=uuid4()),
        event_manager=event_manager,
        client_consumed_queue=consumed,
        expose_error_details=expose_error_details,
    )

    events: list[dict] = []
    while not queue.empty():
        _event_id, payload, _timestamp = queue.get_nowait()
        if payload is not None:
            events.append(json.loads(payload))
    [error_event] = [event for event in events if event["event"] == "error"]
    wire_error = error_event["data"]["error"]
    if expose_error_details:
        assert sensitive_detail in wire_error
    else:
        assert wire_error == "Workflow execution failed."
        assert sensitive_detail not in json.dumps(events)


async def test_v1_advanced_shared_flow_executes_as_caller_without_owner_requery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from langflow.api.v1 import endpoints

    owner_id = uuid4()
    caller_id = uuid4()
    flow = _flow(owner_id=owner_id)
    graph = SimpleNamespace(run_id=None)
    captured: dict = {}

    def fake_from_payload(data, **kwargs):
        captured.update({"data": data, **kwargs})
        return graph

    async def fake_run_graph_internal(**kwargs):
        captured["runtime_graph"] = kwargs["graph"]
        return [], "delegate-session"

    session = SimpleNamespace(
        exec=AsyncMock(side_effect=AssertionError("advanced run must not re-query by owner")),
        in_transaction=lambda: False,
    )
    monkeypatch.setattr(endpoints.Graph, "from_payload", fake_from_payload)
    monkeypatch.setattr(endpoints, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(endpoints, "get_session_service", lambda: SimpleNamespace())
    monkeypatch.setattr(endpoints, "run_graph_internal", fake_run_graph_internal)
    monkeypatch.setattr(endpoints, "get_task_service", lambda: SimpleNamespace(fire_and_forget_task=AsyncMock()))
    monkeypatch.setattr(endpoints, "get_memory_base_service", lambda: SimpleNamespace(on_flow_output=MagicMock()))

    response = await endpoints.experimental_run_flow(
        session=session,
        flow=flow,
        inputs=None,
        outputs=None,
        tweaks=None,
        stream=False,
        session_id=None,
        api_key_user=SimpleNamespace(id=caller_id),
    )

    assert response.status_code == 200
    assert captured["flow_id"] == str(flow.id)
    assert captured["user_id"] == str(caller_id)
    assert captured["runtime_graph"] is graph
    session.exec.assert_not_awaited()


async def test_v1_advanced_non_owner_tweaks_are_hidden_as_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    from langflow.api.v1 import endpoints

    session = SimpleNamespace(
        exec=AsyncMock(return_value=SimpleNamespace(first=lambda: None)),
        in_transaction=lambda: False,
    )
    monkeypatch.setattr(endpoints, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(endpoints, "get_session_service", lambda: SimpleNamespace())
    with pytest.raises(HTTPException) as exc_info:
        await endpoints.experimental_run_flow(
            session=session,
            flow=_flow(owner_id=uuid4()),
            inputs=None,
            outputs=None,
            tweaks={"ChatInput-1": {"input_value": "owner-only override"}},
            stream=False,
            session_id=None,
            api_key_user=SimpleNamespace(id=uuid4()),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Flow not found"
    session.exec.assert_not_awaited()


async def test_webhook_server_generated_tweaks_remain_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    from langflow.api.v1 import endpoints

    generated_tweaks = {"Webhook-1": {"data": '{"trusted":"server mapping"}'}}
    captured: dict = {}

    async def fake_run(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(endpoints, "simple_run_flow", fake_run)
    flow = _flow(owner_id=uuid4())
    await endpoints.simple_run_flow_task(
        flow=flow,
        input_request=SimplifiedAPIRequest(input_value="", tweaks=generated_tweaks),
        api_key_user=SimpleNamespace(id=flow.user_id),
        emit_events=False,
    )

    assert captured["input_request"].tweaks.root == generated_tweaks
