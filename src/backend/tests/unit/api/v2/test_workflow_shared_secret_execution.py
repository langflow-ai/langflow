"""Shared canvas runs keep owner credentials out of requests and event frames."""

from __future__ import annotations

import time
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException, Request
from langflow.api.v1.endpoints import _reject_shared_secret_variable_overrides, _run_flow_internal
from langflow.api.v1.openai_responses import run_flow_for_openai_responses
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.api.v2 import workflow, workflow_execution, workflow_validation
from langflow.services.database.models.flow.model import AccessTypeEnum
from langflow.utils.flow_secrets import strip_secret_field_values
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.converters import ParsedWorkflowRun


def _stored_graph() -> dict:
    return {
        "nodes": [
            {
                "id": "model-node",
                "data": {
                    "node": {
                        "template": {
                            "api_key": {"name": "api_key", "password": True, "value": "owner-secret"},
                            "model_name": {"name": "model_name", "value": "original"},
                        }
                    }
                },
            }
        ],
        "edges": [],
    }


def _value(graph: dict, field: str) -> object:
    return graph["nodes"][0]["data"]["node"]["template"][field]["value"]


def _flow(*, access_type: AccessTypeEnum = AccessTypeEnum.PRIVATE) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        access_type=access_type,
        data=_stored_graph(),
        name="shared-flow",
    )


def test_shared_canvas_validation_keeps_persisted_graph_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = _flow()
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    submitted = strip_secret_field_values(flow.data)
    assert submitted is not None
    submitted["nodes"][0]["position"] = {"x": 20, "y": 30}
    parsed = ParsedWorkflowRun(flow_id=str(flow.id), mode="background", data=submitted)
    monkeypatch.setattr(workflow_validation, "prepare_flow_build_for_user_from_cache", lambda *_args, **_kwargs: None)

    validated = workflow_validation._validate_flow_data_for_execution(parsed, flow, user, expose_error_details=False)

    assert validated.data is not None
    assert _value(validated.data, "api_key") is None
    assert validated.data["nodes"][0]["position"] == {"x": 20, "y": 30}
    assert validated.expose_graph_state is False
    assert validated.emit_v1_side_channel is False
    assert _value(flow.data, "api_key") == "owner-secret"


def test_shared_canvas_rejects_changed_destination_for_restored_key(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = _flow()
    flow.data["nodes"][0]["data"]["node"]["template"]["bing_search_url"] = {
        "name": "bing_search_url",
        "value": "https://provider.example/search",
    }
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    submitted = strip_secret_field_values(flow.data)
    assert submitted is not None
    submitted["nodes"][0]["data"]["node"]["template"]["bing_search_url"]["value"] = "https://attacker.example/collect"
    parsed = ParsedWorkflowRun(flow_id=str(flow.id), mode="stream", data=submitted)
    monkeypatch.setattr(workflow_validation, "prepare_flow_build_for_user_from_cache", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as error:
        workflow_validation._validate_flow_data_for_execution(parsed, flow, user, expose_error_details=False)

    assert error.value.status_code == 400
    assert "owner-secret" not in str(error.value.detail)


@pytest.mark.parametrize("mode", ["sync", "stream", "background"])
def test_shared_run_rejects_destination_tweaks_with_owner_secret(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    flow = _flow()
    flow.data["nodes"][0]["data"]["node"]["template"]["bing_search_url"] = {
        "name": "bing_search_url",
        "value": "https://provider.example/search",
    }
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    submitted = strip_secret_field_values(flow.data) if mode != "sync" else None
    parsed = ParsedWorkflowRun(
        flow_id=str(flow.id),
        mode=mode,
        data=submitted,
        tweaks={"model-node": {"bing_search_url": "https://attacker.example/collect"}},
    )
    monkeypatch.setattr(workflow_validation, "prepare_flow_build_for_user_from_cache", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as error:
        workflow_validation._validate_flow_data_for_execution(parsed, flow, user, expose_error_details=False)

    assert error.value.status_code == 400
    assert "owner-secret" not in str(error.value.detail)


def test_shared_run_rejects_explicit_secret_override_before_scrubbing(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = _flow()
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    submitted = strip_secret_field_values(flow.data)
    assert submitted is not None
    submitted["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] = "editor-secret"
    parsed = ParsedWorkflowRun(flow_id=str(flow.id), mode="background", data=submitted)
    monkeypatch.setattr(workflow_validation, "prepare_flow_build_for_user_from_cache", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as error:
        workflow_validation._validate_flow_data_for_execution(parsed, flow, user, expose_error_details=False)

    assert error.value.status_code == 400
    assert "editor-secret" not in str(error.value.detail)


def test_shared_run_rejects_body_global_that_could_redirect_owner_key() -> None:
    flow = _flow()
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    parsed = ParsedWorkflowRun(
        flow_id=str(flow.id),
        mode="sync",
        globals={"DESTINATION_URL": "https://attacker.example/collect"},
    )

    with pytest.raises(HTTPException) as error:
        workflow_validation._validate_flow_data_for_execution(parsed, flow, user, expose_error_details=False)

    assert error.value.status_code == 400
    assert "owner-secret" not in str(error.value.detail)


async def test_shared_sync_run_rejects_header_global_before_graph_build() -> None:
    flow = _flow()
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    parsed = ParsedWorkflowRun(flow_id=str(flow.id), mode="sync")
    request = Request(
        {"type": "http", "headers": [(b"x-langflow-global-var-destination_url", b"https://attacker.example/collect")]}
    )

    with pytest.raises(HTTPException) as error:
        await workflow_execution.execute_sync_workflow(
            parsed,
            flow,
            uuid4(),
            user,
            BackgroundTasks(),
            request,
        )

    assert error.value.status_code == 400
    assert "owner-secret" not in str(error.value.detail)


def test_v1_shared_run_rejects_variable_context_with_owner_secret() -> None:
    flow = _flow()
    user = SimpleNamespace(id=uuid4(), is_superuser=False)

    with pytest.raises(HTTPException) as error:
        _reject_shared_secret_variable_overrides(
            flow,
            user,
            {"DESTINATION_URL": "https://attacker.example/collect"},
        )

    assert error.value.status_code == 400


@pytest.mark.parametrize("source", ["header", "context"])
async def test_v1_run_rejects_variable_override_before_streaming(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    from langflow.api.v1 import endpoints

    flow = _flow()
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    variables = {"DESTINATION_URL": "https://attacker.example/collect"}
    headers = (
        [(b"x-langflow-global-var-destination_url", b"https://attacker.example/collect")] if source == "header" else []
    )
    request = Request({"type": "http", "headers": headers})
    context = {"request_variables": variables} if source == "context" else None
    monkeypatch.setattr(endpoints, "get_telemetry_service", lambda: SimpleNamespace())

    with pytest.raises(HTTPException) as error:
        await _run_flow_internal(
            background_tasks=BackgroundTasks(),
            flow=flow,
            input_request=SimplifiedAPIRequest(input_value="hello"),
            stream=True,
            api_key_user=user,
            context=context,
            http_request=request,
        )

    assert error.value.status_code == 400


async def test_openai_responses_rejects_variable_context_before_graph_validation() -> None:
    flow = _flow()
    user = SimpleNamespace(id=uuid4(), is_superuser=False)

    with pytest.raises(HTTPException) as error:
        await run_flow_for_openai_responses(
            flow,
            SimpleNamespace(),
            user,
            variables={"DESTINATION_URL": "https://attacker.example/collect"},
        )

    assert error.value.status_code == 400


def test_shared_stored_graph_sanitization_does_not_persist_owner_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = _flow()
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    parsed = ParsedWorkflowRun(flow_id=str(flow.id), mode="background")
    monkeypatch.setattr(
        workflow_validation,
        "prepare_flow_build_for_user_from_cache",
        lambda graph, **_kwargs: deepcopy(graph),
    )

    validated = workflow_validation._validate_flow_data_for_execution(parsed, flow, user, expose_error_details=False)

    assert validated.data is not None
    assert _value(validated.data, "api_key") is None


async def test_background_request_persists_only_redacted_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = _flow()
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    submitted = strip_secret_field_values(flow.data)
    assert submitted is not None
    parsed = ParsedWorkflowRun(flow_id=str(flow.id), mode="background", data=submitted)
    monkeypatch.setattr(workflow_validation, "flow_data_override_allowed", lambda: True)
    monkeypatch.setattr(workflow_validation, "prepare_flow_build_for_user_from_cache", lambda *_args, **_kwargs: None)
    validated = workflow._apply_execution_gates(parsed, flow, user)
    service = SimpleNamespace(_frame_source_factory=lambda: None, submit=AsyncMock(return_value=uuid4()))
    monkeypatch.setattr(workflow, "get_background_execution_service", lambda: service)

    await workflow.execute_workflow_background(
        parsed=validated,
        flow=flow,
        job_id=uuid4(),
        current_user=user,
        http_request=None,
        stream_protocol="agui",
    )

    persisted = service.submit.await_args.kwargs["request"]
    assert _value(persisted["data"], "api_key") is None
    assert persisted["expose_graph_state"] is False
    assert "owner-secret" not in str(persisted)


@pytest.mark.parametrize(
    ("access_type", "protocol", "expected_secret"),
    [
        (AccessTypeEnum.PRIVATE, "v2", "owner-secret"),
        (AccessTypeEnum.PUBLIC, "v2.public", None),
    ],
)
async def test_stream_build_restores_only_private_shared_graph(
    monkeypatch: pytest.MonkeyPatch,
    access_type: AccessTypeEnum,
    protocol: str,
    expected_secret: str | None,
) -> None:
    flow = _flow(access_type=access_type)
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    submitted = strip_secret_field_values(flow.data)
    assert submitted is not None
    submitted["nodes"][0]["position"] = {"x": 20, "y": 30}
    parsed = ParsedWorkflowRun(
        flow_id=str(flow.id), mode="stream", data=submitted, expose_graph_state=False, emit_v1_side_channel=False
    )
    seen: list[dict] = []

    async def capture_build(**kwargs) -> None:
        graph = kwargs["data"].model_dump()
        seen.append(graph)
        kwargs["event_manager"].send_event(
            event_type="end_vertex",
            data={"build_data": {"inputs": {"api_key": "owner-secret"}}},
        )
        kwargs["event_manager"].on_end(data={})
        await kwargs["event_manager"].queue.put((None, None, time.time()))

    monkeypatch.setattr(workflow_execution, "generate_flow_events", capture_build)
    adapter = get_stream_adapter(
        "agui",
        StreamAdapterContext(run_id="run", thread_id="thread", expose_graph_state=False),
    )

    frames = [
        frame
        async for frame, _event_type in workflow_execution._stream_event_frames(
            adapter=adapter,
            flow_id=flow.id,
            flow_name=flow.name,
            background_tasks=BackgroundTasks(),
            parsed=parsed,
            current_user=user,
            provider_policy_flow=flow,
            source_flow_owner_id=flow.user_id,
            protocol=protocol,
        )
    ]

    assert _value(seen[0], "api_key") == expected_secret
    assert seen[0]["nodes"][0]["position"] == {"x": 20, "y": 30}
    assert _value(parsed.data, "api_key") is None
    assert "owner-secret" not in b"".join(frames).decode()


async def test_stream_restores_secret_after_trusted_component_source_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = _flow()
    flow.data["nodes"][0]["data"]["node"]["template"]["code"] = {
        "name": "code",
        "value": "# stale stored source",
    }
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    submitted = strip_secret_field_values(flow.data)
    assert submitted is not None
    submitted["nodes"][0]["position"] = {"x": 20, "y": 30}

    def trusted_substitution(graph: dict, *, is_superuser: bool) -> dict:
        assert not is_superuser
        trusted = deepcopy(graph)
        trusted["nodes"][0]["data"]["node"]["template"]["code"]["value"] = "# trusted server source"
        return trusted

    monkeypatch.setattr(workflow_validation, "prepare_flow_build_for_user_from_cache", trusted_substitution)
    monkeypatch.setattr(workflow_execution, "prepare_flow_build_for_user_from_cache", trusted_substitution)
    parsed = workflow_validation._validate_flow_data_for_execution(
        ParsedWorkflowRun(flow_id=str(flow.id), mode="stream", data=submitted),
        flow,
        user,
        expose_error_details=False,
    )
    assert parsed.data is not None
    assert _value(parsed.data, "api_key") is None

    seen: list[dict] = []

    async def capture_build(**kwargs) -> None:
        seen.append(kwargs["data"].model_dump())
        kwargs["event_manager"].on_end(data={})
        await kwargs["event_manager"].queue.put((None, None, time.time()))

    monkeypatch.setattr(workflow_execution, "generate_flow_events", capture_build)
    adapter = get_stream_adapter(
        "agui",
        StreamAdapterContext(run_id="run", thread_id="thread", expose_graph_state=False),
    )
    frames = [
        frame
        async for frame, _event_type in workflow_execution._stream_event_frames(
            adapter=adapter,
            flow_id=flow.id,
            flow_name=flow.name,
            background_tasks=BackgroundTasks(),
            parsed=parsed,
            current_user=user,
            provider_policy_flow=flow,
            source_flow_owner_id=flow.user_id,
            protocol="v2",
        )
    ]

    assert _value(seen[0], "api_key") == "owner-secret"
    assert _value(seen[0], "code") == "# trusted server source"
    assert _value(flow.data, "code") == "# stale stored source"
    assert "owner-secret" not in b"".join(frames).decode()
