from __future__ import annotations

import asyncio
import copy
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
async def test_run_flow_generator_error_depends_on_explicit_policy(
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


@pytest.mark.parametrize("caller_kind", ["delegate", "owner"])
async def test_v1_run_stream_route_derives_error_policy_from_flow_ownership(
    monkeypatch: pytest.MonkeyPatch,
    caller_kind: str,
) -> None:
    from langflow.api.v1 import endpoints

    owner_id = uuid4()
    caller_id = owner_id if caller_kind == "owner" else uuid4()
    captured: dict = {}

    async def capture_run(**kwargs):
        captured.update(kwargs)
        await kwargs["event_manager"].queue.put((None, None, 0.0))

    monkeypatch.setattr(endpoints, "run_flow_generator", capture_run)
    monkeypatch.setattr(
        endpoints,
        "get_telemetry_service",
        lambda: SimpleNamespace(log_package_run=AsyncMock()),
    )

    response = await endpoints._run_flow_internal(
        background_tasks=BackgroundTasks(),
        flow=_flow(owner_id=owner_id),
        input_request=SimplifiedAPIRequest(input_value="hello"),
        stream=True,
        api_key_user=SimpleNamespace(id=caller_id),
        context=None,
        http_request=_request(),
    )
    _ = [chunk async for chunk in response.body_iterator]
    if response.background is not None:
        await response.background()

    assert captured["expose_error_details"] is (caller_kind == "owner")


@pytest.mark.parametrize("caller_kind", ["delegate", "owner"])
async def test_v1_run_sync_error_depends_on_flow_ownership(
    monkeypatch: pytest.MonkeyPatch,
    caller_kind: str,
) -> None:
    from langflow.api.v1 import endpoints

    sensitive_detail = "owner-sync-provider-secret"
    sensitive_component_id = "PrivateProviderNode-secret-id"
    owner_id = uuid4()
    caller_id = owner_id if caller_kind == "owner" else uuid4()
    flow = _flow(
        owner_id=owner_id,
        data={
            "nodes": [
                {
                    "id": sensitive_component_id,
                    "data": {"node": {"lf_version": "0.0.0"}},
                }
            ],
            "edges": [],
        },
    )

    async def fail_run(**_kwargs):
        raise RuntimeError(sensitive_detail)

    monkeypatch.setattr(endpoints, "simple_run_flow", fail_run)
    monkeypatch.setattr(
        endpoints,
        "get_telemetry_service",
        lambda: SimpleNamespace(log_package_run=AsyncMock()),
    )

    with pytest.raises(HTTPException) as exc_info:
        await endpoints._run_flow_internal(
            background_tasks=BackgroundTasks(),
            flow=flow,
            input_request=SimplifiedAPIRequest(input_value="hello"),
            stream=False,
            api_key_user=SimpleNamespace(id=caller_id),
            context=None,
            http_request=_request(),
        )

    if caller_kind == "owner":
        assert sensitive_detail in str(exc_info.value.detail)
        assert sensitive_component_id in str(exc_info.value.detail)
    else:
        assert "Workflow execution failed." in str(exc_info.value.detail)
        assert sensitive_detail not in str(exc_info.value.detail)
        assert sensitive_component_id not in str(exc_info.value.detail)


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
        commit=AsyncMock(),
    )
    task_service = SimpleNamespace(fire_and_forget_task=AsyncMock())
    monkeypatch.setattr(endpoints.Graph, "from_payload", fake_from_payload)
    monkeypatch.setattr(endpoints, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(endpoints, "get_session_service", lambda: SimpleNamespace())
    monkeypatch.setattr(endpoints, "run_graph_internal", fake_run_graph_internal)
    monkeypatch.setattr(endpoints, "get_task_service", lambda: task_service)
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
    task_service.fire_and_forget_task.assert_not_awaited()


@pytest.mark.parametrize("cache_mismatch", ["component_principal", "flow_identity"])
async def test_v1_advanced_shared_session_rebuilds_mismatched_real_graph_for_caller(
    monkeypatch: pytest.MonkeyPatch,
    cache_mismatch: str,
) -> None:
    from langflow.api.v1 import endpoints
    from lfx.components.input_output.chat import ChatInput

    owner_id = uuid4()
    caller_id = uuid4()
    flow_data = {
        "nodes": [ChatInput(_id="ChatInput-execution-principal").to_frontend_node()],
        "edges": [],
    }
    flow = _flow(owner_id=owner_id, data=copy.deepcopy(flow_data))
    cached_component_user_id = owner_id if cache_mismatch == "component_principal" else caller_id
    cached_flow_id = flow.id if cache_mismatch == "component_principal" else uuid4()
    cached_graph = endpoints.Graph.from_payload(
        copy.deepcopy(flow_data),
        flow_id=str(cached_flow_id),
        user_id=str(cached_component_user_id),
        flow_name=flow.name,
    )
    cached_components = [vertex.custom_component for vertex in cached_graph.vertices if vertex.custom_component]
    assert cached_components
    assert all(str(component.user_id) == str(cached_component_user_id) for component in cached_components)

    if cache_mismatch == "component_principal":
        # Reproduce the old unsafe "fix": the graph principal changes while its
        # already-instantiated components retain the owner's credential principal.
        cached_graph.user_id = str(caller_id)
        assert all(str(component.user_id) == str(owner_id) for component in cached_components)
    captured: dict = {}

    async def fake_run_graph_internal(**kwargs):
        captured.update(kwargs)
        return [], "delegate-session"

    session = SimpleNamespace(in_transaction=lambda: False, commit=AsyncMock())
    session_service = SimpleNamespace(load_session=AsyncMock(return_value=(cached_graph, None)))
    monkeypatch.setattr(endpoints, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(endpoints, "get_session_service", lambda: session_service)
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
        session_id=str(flow.id),
        api_key_user=SimpleNamespace(id=caller_id),
    )

    assert response.status_code == 200
    caller_graph = captured["graph"]
    assert caller_graph is not cached_graph
    assert caller_graph.flow_id == str(flow.id)
    assert caller_graph.user_id == str(caller_id)
    caller_components = [vertex.custom_component for vertex in caller_graph.vertices if vertex.custom_component]
    assert caller_components
    assert all(str(component.user_id) == str(caller_id) for component in caller_components)


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


async def test_v1_advanced_owner_tweaks_do_not_mutate_loaded_flow_data(monkeypatch: pytest.MonkeyPatch) -> None:
    from langflow.api.v1 import endpoints

    owner_id = uuid4()
    flow = _flow(
        owner_id=owner_id,
        data={"nodes": [{"id": "Component-1", "data": {"value": "stored"}}], "edges": []},
    )
    original_data = copy.deepcopy(flow.data)
    captured: dict = {}

    def mutating_process_tweaks(graph_data, _tweaks):
        graph_data["nodes"][0]["data"]["value"] = "request override"
        return graph_data

    def fake_from_payload(graph_data, **_kwargs):
        captured["graph_data"] = graph_data
        return SimpleNamespace(run_id=None)

    monkeypatch.setattr(endpoints, "process_tweaks", mutating_process_tweaks)
    monkeypatch.setattr(endpoints.Graph, "from_payload", fake_from_payload)
    monkeypatch.setattr(endpoints, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(endpoints, "run_graph_internal", AsyncMock(return_value=([], "owner-session")))
    monkeypatch.setattr(endpoints, "get_task_service", lambda: SimpleNamespace(fire_and_forget_task=AsyncMock()))
    monkeypatch.setattr(endpoints, "get_memory_base_service", lambda: SimpleNamespace(on_flow_output=MagicMock()))

    response = await endpoints.experimental_run_flow(
        session=SimpleNamespace(in_transaction=lambda: False, commit=AsyncMock()),
        flow=flow,
        inputs=None,
        outputs=None,
        tweaks={"Component-1": {"value": "request override"}},
        stream=False,
        session_id=None,
        api_key_user=SimpleNamespace(id=owner_id),
    )

    assert response.status_code == 200
    assert flow.data == original_data
    assert captured["graph_data"]["nodes"][0]["data"]["value"] == "request override"


@pytest.mark.parametrize("caller_kind", ["delegate", "owner"])
async def test_v1_advanced_http_validation_error_depends_on_flow_ownership(
    monkeypatch: pytest.MonkeyPatch,
    caller_kind: str,
) -> None:
    from langflow.api.v1 import endpoints

    sensitive_detail = "owner-HITL-validation-detail"
    owner_id = uuid4()
    caller_id = owner_id if caller_kind == "owner" else uuid4()
    session = SimpleNamespace(in_transaction=lambda: False)

    monkeypatch.setattr(endpoints, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(
        endpoints,
        "raise_if_hitl_unsupported",
        MagicMock(side_effect=HTTPException(status_code=400, detail=sensitive_detail)),
    )

    with pytest.raises(HTTPException) as exc_info:
        await endpoints.experimental_run_flow(
            session=session,
            flow=_flow(owner_id=owner_id),
            inputs=None,
            outputs=None,
            tweaks=None,
            stream=False,
            session_id=None,
            api_key_user=SimpleNamespace(id=caller_id),
        )

    if caller_kind == "owner":
        assert exc_info.value.status_code == 400
        assert sensitive_detail in str(exc_info.value.detail)
    else:
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Workflow execution failed."
        assert sensitive_detail not in str(exc_info.value.detail)


@pytest.mark.parametrize("caller_kind", ["delegate", "owner"])
async def test_v1_advanced_missing_data_error_depends_on_flow_ownership(
    monkeypatch: pytest.MonkeyPatch,
    caller_kind: str,
) -> None:
    from langflow.api.v1 import endpoints

    owner_id = uuid4()
    caller_id = owner_id if caller_kind == "owner" else uuid4()
    flow = _flow(owner_id=owner_id)
    flow.data = None
    session = SimpleNamespace(in_transaction=lambda: False)
    monkeypatch.setattr(endpoints, "ensure_flow_permission", AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        await endpoints.experimental_run_flow(
            session=session,
            flow=flow,
            inputs=None,
            outputs=None,
            tweaks=None,
            stream=False,
            session_id=None,
            api_key_user=SimpleNamespace(id=caller_id),
        )

    if caller_kind == "owner":
        assert exc_info.value.status_code == 404
        assert str(flow.id) in str(exc_info.value.detail)
    else:
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Workflow execution failed."
        assert str(flow.id) not in str(exc_info.value.detail)


@pytest.mark.parametrize("caller_kind", ["delegate", "owner"])
async def test_v1_advanced_error_depends_on_flow_ownership(
    monkeypatch: pytest.MonkeyPatch,
    caller_kind: str,
) -> None:
    from langflow.api.v1 import endpoints

    sensitive_detail = "owner-advanced-provider-secret"
    owner_id = uuid4()
    caller_id = owner_id if caller_kind == "owner" else uuid4()
    graph = SimpleNamespace(run_id=None)
    session = SimpleNamespace(in_transaction=lambda: False, commit=AsyncMock())

    monkeypatch.setattr(endpoints, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(endpoints.Graph, "from_payload", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(endpoints, "run_graph_internal", AsyncMock(side_effect=RuntimeError(sensitive_detail)))

    with pytest.raises(HTTPException) as exc_info:
        await endpoints.experimental_run_flow(
            session=session,
            flow=_flow(owner_id=owner_id),
            inputs=None,
            outputs=None,
            tweaks=None,
            stream=False,
            session_id=None,
            api_key_user=SimpleNamespace(id=caller_id),
        )

    if caller_kind == "owner":
        assert sensitive_detail in str(exc_info.value.detail)
    else:
        assert exc_info.value.detail == "Workflow execution failed."
        assert sensitive_detail not in str(exc_info.value.detail)


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
    assert captured["expose_error_details"] is True
