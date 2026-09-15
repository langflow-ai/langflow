"""Restricted component substitutions remain visible through the workflow stream."""

import json
import time
from copy import deepcopy
from importlib.resources import files
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from langflow.api.v2.workflow_validation import _validate_flow_data_for_execution
from lfx.interface import components
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
