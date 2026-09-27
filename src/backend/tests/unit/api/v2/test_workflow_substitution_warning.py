"""Restricted component substitutions remain visible in workflow results and streams."""

import json
import time
from copy import deepcopy
from importlib.resources import files
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from langflow.api.v2.workflow_validation import _validate_flow_data_for_execution
from lfx.graph.exceptions import GraphPausedException
from lfx.interface import components
from lfx.schema.workflow import JobStatus, WorkflowExecutionResponse
from lfx.services.deps import get_settings_service
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.converters import ParsedWorkflowRun


@pytest.fixture
def custom_agent_flow(monkeypatch):
    registry = dict(json.loads(files("lfx").joinpath("_assets/component_index.json").read_text())["entries"])
    cache = components.ComponentCache()
    cache.all_types_dict = registry
    cache.all_types_ready = True
    monkeypatch.setattr(components, "component_cache", cache)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", False)
    monkeypatch.setattr(settings, "custom_component_admin_only", True)
    monkeypatch.setattr(settings, "substitute_outdated_component_code", True)
    saved = deepcopy(registry["models_and_agents"]["Agent"])
    saved["template"]["code"]["value"] += "\n# QA customized method body\n"
    data = {"nodes": [{"id": "Agent-qa", "data": {"id": "Agent-qa", "type": "Agent", "node": saved}}], "edges": []}
    return SimpleNamespace(id=uuid4(), name="Policy test", data=data)


@pytest.mark.parametrize("inline", [False, True], ids=["stored", "inline"])
@pytest.mark.parametrize("is_superuser", [False, True], ids=["editor", "admin"])
@pytest.mark.parametrize("change_inputs", [False, True], ids=["code-only", "forked-inputs"])
def test_warning_survives_caller_aware_sanitization(custom_agent_flow, inline, is_superuser, change_inputs):
    flow = custom_agent_flow
    if change_inputs:
        flow.data["nodes"][0]["data"]["node"]["template"].pop("model")
    original = deepcopy(flow.data)
    parsed = ParsedWorkflowRun(flow_id=str(flow.id), data=flow.data if inline else None)

    gated = _validate_flow_data_for_execution(
        parsed, flow, SimpleNamespace(is_superuser=is_superuser), expose_error_details=True
    )

    assert "LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false" in gated.component_substitution_warning
    assert "Agent (Agent-qa)" in gated.component_substitution_warning
    assert flow.data == original
    if not is_superuser:
        assert (
            gated.data["nodes"][0]["data"]["node"]["template"]["code"]["value"]
            != (original["nodes"][0]["data"]["node"]["template"]["code"]["value"])
        )


def test_execute_only_warning_omits_component_names(custom_agent_flow):
    gated = _validate_flow_data_for_execution(
        ParsedWorkflowRun(flow_id=str(custom_agent_flow.id)),
        custom_agent_flow,
        SimpleNamespace(is_superuser=False),
        expose_error_details=False,
    )
    assert gated.component_substitution_warning is not None
    assert "Agent" not in gated.component_substitution_warning
    assert "Ask the flow owner" in gated.component_substitution_warning


@pytest.mark.parametrize("outcome", ["completed", "failed", "suspended", "unmodified"])
async def test_sync_response_preserves_warning_without_changing_status(custom_agent_flow, monkeypatch, outcome):
    from langflow.api.v2 import workflow_execution
    from langflow.services import deps

    flow = custom_agent_flow
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    if outcome == "unmodified":
        flow.data["nodes"][0]["data"]["node"] = deepcopy(
            components.component_cache.all_types_dict["models_and_agents"]["Agent"]
        )
    parsed = _validate_flow_data_for_execution(
        ParsedWorkflowRun(flow_id=str(flow.id), mode="sync"), flow, user, expose_error_details=True
    )
    graph = MagicMock()
    graph.get_terminal_nodes.return_value = []
    job_service = SimpleNamespace(
        create_job=AsyncMock(),
        execute_with_status=AsyncMock(return_value=([], "session-1")),
        update_job_status=AsyncMock(),
    )
    if outcome == "failed":
        job_service.execute_with_status.side_effect = RuntimeError("Component failed")
    elif outcome == "suspended":
        job_service.execute_with_status.side_effect = GraphPausedException(
            checkpoint_id="checkpoint-1", reason="waiting on a human", data={"request_id": "request-1"}
        )
    monkeypatch.setattr(workflow_execution, "warm_deepcopy", AsyncMock(return_value=None))
    monkeypatch.setattr(workflow_execution.Graph, "from_payload", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(workflow_execution, "get_job_service", lambda: job_service)
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: SimpleNamespace(log_package_run=AsyncMock()))

    response = await workflow_execution.execute_sync_workflow(
        parsed=parsed,
        flow=flow,
        job_id=uuid4(),
        current_user=user,
        background_tasks=BackgroundTasks(),
        http_request=None,
        expose_error_details=True,
    )
    body = response.model_dump(mode="json")
    assert body["status"] == ("completed" if outcome == "unmodified" else outcome)
    assert body["has_errors"] == (outcome == "failed")
    assert body["warnings"] == ([] if outcome == "unmodified" else [parsed.component_substitution_warning])
    if outcome != "unmodified":
        metadata = job_service.create_job.await_args.kwargs["initial_metadata"]
        assert metadata["component_substitution_warning"] == parsed.component_substitution_warning


@pytest.mark.parametrize("source", ["sync", "background", "legacy"])
@pytest.mark.parametrize("stored_outputs", [True, False])
async def test_completed_status_preserves_warning(custom_agent_flow, monkeypatch, source, stored_outputs):
    from langflow.api.v2 import workflow

    flow = custom_agent_flow
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    flow.user_id = user.id
    warning = "Custom components are disabled. This run uses the server's component code."
    metadata = {
        "sync": {"component_substitution_warning": warning},
        "background": {"request": {"component_substitution_warning": warning}},
        "legacy": {},
    }[source]
    output = {"component_id": "output-1", "type": "message", "status": "completed", "content": "Hello"}
    job = SimpleNamespace(
        flow_id=flow.id,
        type=workflow.JobType.WORKFLOW,
        status=JobStatus.COMPLETED,
        job_metadata=metadata,
        result={"outputs": [output]} if stored_outputs else None,
    )
    monkeypatch.setattr(
        workflow, "get_job_service", lambda: SimpleNamespace(get_job_by_job_id=AsyncMock(return_value=job))
    )
    monkeypatch.setattr(workflow, "get_flow_by_id_or_endpoint_name", AsyncMock(return_value=flow))
    monkeypatch.setattr(workflow, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(
        workflow,
        "reconstruct_workflow_response_from_job_id",
        AsyncMock(return_value=WorkflowExecutionResponse(flow_id=str(flow.id), status=JobStatus.COMPLETED)),
    )

    response = await workflow.get_workflow_status(http_request=None, current_user=user, job_id=uuid4(), session=None)

    assert response.model_dump(mode="json")["warnings"] == ([] if source == "legacy" else [warning])
    assert response.status == JobStatus.COMPLETED


async def test_background_worker_preserves_the_warning_after_serialization(custom_agent_flow, monkeypatch):
    from langflow.api.v2 import workflow

    flow = custom_agent_flow
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    parsed = _validate_flow_data_for_execution(
        ParsedWorkflowRun(flow_id=str(flow.id), mode="background"), flow, user, expose_error_details=True
    )
    service = SimpleNamespace(_frame_source_factory=None, submit=AsyncMock(return_value=uuid4()))
    monkeypatch.setattr(workflow, "get_background_execution_service", lambda: service)

    await workflow.execute_workflow_background(
        parsed=parsed, flow=flow, job_id=uuid4(), current_user=user, http_request=None, stream_protocol="agui"
    )
    request = service.submit.await_args.kwargs["request"]
    restored = workflow._parse_persisted_workflow_request(json.loads(json.dumps(request)))

    assert restored.component_substitution_warning == parsed.component_substitution_warning
    assert "Agent (Agent-qa)" in restored.component_substitution_warning
    assert restored.data == parsed.data


@pytest.mark.parametrize("protocol", ["agui", "langflow"])
async def test_warning_is_streamed_before_success(custom_agent_flow, monkeypatch, protocol):
    from langflow.api.v2 import workflow_execution
    from langflow.services import deps

    flow = custom_agent_flow
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    parsed = _validate_flow_data_for_execution(
        ParsedWorkflowRun(flow_id=str(flow.id)), flow, user, expose_error_details=True
    )

    async def finish_run(**kwargs):
        manager = kwargs["event_manager"]
        manager.on_end(data={})
        await manager.queue.put((None, None, time.time()))

    monkeypatch.setattr(workflow_execution, "generate_flow_events", finish_run)
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: SimpleNamespace(log_package_run=AsyncMock()))
    adapter = get_stream_adapter(protocol, StreamAdapterContext(run_id="run-1", thread_id="thread-1"))
    frames = [
        (frame, event_type)
        async for frame, event_type in workflow_execution._stream_event_frames(
            adapter=adapter,
            flow_id=flow.id,
            flow_name=flow.name,
            background_tasks=BackgroundTasks(),
            parsed=parsed,
            current_user=user,
            protocol=protocol,
            execution_timeout=None,
        )
    ]
    events = [
        json.loads(line[6:]) for frame, _ in frames for line in frame.decode().splitlines() if line.startswith("data:")
    ]
    if protocol == "agui":
        warnings = [event for event in events if event.get("name") == "langflow.warning"]
        assert len(warnings) == 1
        assert warnings[0]["value"]["message"] == parsed.component_substitution_warning
        assert events[-1]["type"] == "RUN_FINISHED"
        assert not any(event["type"] == "RUN_ERROR" for event in events)
        assert adapter.is_durable("CUSTOM")
    else:
        assert events[0] == {"event": "warning", "data": {"message": parsed.component_substitution_warning}}
        assert events[-1]["event"] == "end"
        assert adapter.is_durable("warning")


@pytest.mark.parametrize("cache_result", [False, True])
async def test_sync_http_run_and_status_warn_for_real_substitution(
    client, created_api_key, custom_agent_flow, monkeypatch, cache_result
):
    """A rejected code-only edit still succeeds with stock code and warns on POST and GET."""
    from langflow.services.database.models.flow.model import Flow
    from lfx.services.deps import session_scope

    monkeypatch.setattr(get_settings_service().settings, "sync_result_storage_enabled", cache_result)
    saved = deepcopy(components.component_cache.all_types_dict["input_output"]["ChatInput"])
    signature = "async def message_response(self) -> Message:\n"
    code = saved["template"]["code"]["value"]
    assert signature in code
    saved["template"]["code"]["value"] = code.replace(
        signature, signature + '        raise RuntimeError("CUSTOM_CODE_RAN")\n', 1
    )
    saved["template"]["should_store_message"]["value"] = False
    payload = {
        "nodes": [{"id": "ChatInput-qa", "data": {"id": "ChatInput-qa", "type": "ChatInput", "node": saved}}],
        "edges": [],
    }
    flow_id = custom_agent_flow.id
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name="Sync policy warning", data=payload, user_id=created_api_key.user_id))

    headers = {"x-api-key": created_api_key.api_key}
    try:
        response = await client.post(
            "api/v2/workflows",
            json={"flow_id": str(flow_id), "mode": "sync", "input_value": "Hello"},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed", body
        assert not body["has_errors"]
        assert len(body["warnings"]) == 1
        assert "LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false" in body["warnings"][0]
        assert "Chat Input (ChatInput-qa)" in body["warnings"][0]

        status = await client.get("api/v2/workflows", params={"job_id": body["job_id"]}, headers=headers)
        assert status.status_code == 200, status.text
        assert status.json()["warnings"] == body["warnings"]

        async with session_scope() as session:
            stored = await session.get(Flow, flow_id)
            assert stored.data == payload
    finally:
        async with session_scope() as session:
            stored = await session.get(Flow, flow_id)
            if stored:
                await session.delete(stored)
