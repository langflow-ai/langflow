"""Regressions for admin-only policy on V2 inline workflow execution."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from lfx.workflow.converters import ParsedWorkflowRun


def _execution_context(*, mode: str):
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    flow = SimpleNamespace(id=uuid4(), user_id=user.id, data=None)
    parsed = ParsedWorkflowRun(
        flow_id=str(flow.id),
        mode=mode,
        data={"nodes": [{"id": "known", "data": {"source": "request"}}], "edges": []},
    )
    return parsed, flow, user


def test_v2_stream_passes_sanitized_inline_data_to_execution(monkeypatch):
    """Live streaming must not retain the caller's code bytes after validation."""
    from langflow.api.v2 import workflow as workflow_module
    from langflow.api.v2 import workflow_validation

    parsed, flow, user = _execution_context(mode="stream")
    sanitized = {"nodes": [{"id": "known", "data": {"source": "server"}}], "edges": []}
    execute = MagicMock(return_value=object())

    def sanitize(_data, *, is_superuser):
        assert is_superuser is False
        return sanitized

    monkeypatch.setattr(
        workflow_validation,
        "prepare_flow_build_for_user_from_cache",
        sanitize,
    )
    monkeypatch.setattr(workflow_module, "get_stream_adapter", MagicMock(return_value=object()))
    monkeypatch.setattr(workflow_module, "_execute_streaming_workflow", execute)

    workflow_module.build_stream_response(
        parsed,
        flow,
        user,
        stream_protocol="langflow",
        background_tasks=MagicMock(),
    )

    assert execute.call_args.kwargs["parsed"].data == sanitized
    assert parsed.data["nodes"][0]["data"]["source"] == "request"


def _stored_execution_context(*, mode: str):
    """A stored-graph request: the caller sends no ``data`` at all."""
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    stored = {
        "nodes": [
            {
                "id": "ChatInput-1",
                "data": {
                    "id": "ChatInput-1",
                    "type": "ChatInput",
                    "node": {"template": {"code": {"value": "# stored source"}}},
                },
            }
        ],
        "edges": [],
    }
    flow = SimpleNamespace(id=uuid4(), user_id=user.id, data=stored)
    parsed = ParsedWorkflowRun(flow_id=str(flow.id), mode=mode, data=None)
    return parsed, flow, user


def _sanitized_stored_graph() -> dict:
    return {
        "nodes": [
            {
                "id": "ChatInput-1",
                "data": {
                    "id": "ChatInput-1",
                    "type": "ChatInput",
                    "node": {"template": {"code": {"value": "# trusted server source"}}},
                },
            }
        ],
        "edges": [],
    }


@pytest.mark.parametrize("mode", ["sync", "stream", "background"])
def test_v2_stored_graph_runs_the_caller_aware_policy(monkeypatch, mode):
    """Stored graphs must face the same caller-aware policy as inline request data.

    Without this, a regular user persists modified component source through the
    ordinary flow-write API and executes it by omitting ``data`` from the request.
    """
    from langflow.api.v2 import workflow as workflow_module
    from langflow.api.v2 import workflow_validation

    parsed, flow, user = _stored_execution_context(mode=mode)
    sanitized = _sanitized_stored_graph()
    seen: dict = {}

    def sanitize(data, *, is_superuser):
        seen["validated"] = data
        assert is_superuser is False
        return sanitized

    monkeypatch.setattr(workflow_validation, "prepare_flow_build_for_user_from_cache", sanitize)

    gated = workflow_module._apply_execution_gates(parsed, flow, user)

    assert seen["validated"] == flow.data
    assert gated.data == sanitized
    # The stored row itself is never rewritten.
    assert flow.data["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "# stored source"


@pytest.mark.parametrize("mode", ["sync", "stream", "background"])
def test_v2_stored_graph_policy_denial_becomes_400(monkeypatch, mode):
    """A policy rejection on the stored graph stops execution with a client error."""
    from fastapi import HTTPException
    from langflow.api.v2 import workflow as workflow_module
    from langflow.api.v2 import workflow_validation
    from lfx.utils.flow_validation import CustomComponentValidationError

    parsed, flow, user = _stored_execution_context(mode=mode)

    def reject(_data, *, is_superuser):
        assert is_superuser is False
        message = "custom components are restricted to administrators"
        raise CustomComponentValidationError(message)

    monkeypatch.setattr(workflow_validation, "prepare_flow_build_for_user_from_cache", reject)

    with pytest.raises(HTTPException) as excinfo:
        workflow_module._apply_execution_gates(parsed, flow, user)

    assert excinfo.value.status_code == 400


@pytest.mark.parametrize("mode", ["sync", "stream", "background"])
def test_v2_stored_graph_permissive_policy_leaves_request_untouched(monkeypatch, mode):
    """With no caller-specific restriction the request still executes from the stored row."""
    from langflow.api.v2 import workflow as workflow_module
    from langflow.api.v2 import workflow_validation

    def permissive(_data, *, is_superuser):
        assert is_superuser is False

    parsed, flow, user = _stored_execution_context(mode=mode)
    monkeypatch.setattr(workflow_validation, "prepare_flow_build_for_user_from_cache", permissive)

    gated = workflow_module._apply_execution_gates(parsed, flow, user)

    assert gated.data is None


@pytest.mark.asyncio
async def test_v2_background_persists_only_sanitized_inline_data(monkeypatch):
    """Durable background requests must queue the trusted server payload."""
    from langflow.api.v2 import workflow as workflow_module
    from langflow.api.v2 import workflow_validation

    parsed, flow, user = _execution_context(mode="background")
    sanitized = {"nodes": [{"id": "known", "data": {"source": "server"}}], "edges": []}
    execute = AsyncMock(return_value=object())

    def sanitize(_data, *, is_superuser):
        assert is_superuser is False
        return sanitized

    monkeypatch.setattr(
        workflow_validation,
        "prepare_flow_build_for_user_from_cache",
        sanitize,
    )
    monkeypatch.setattr(workflow_module, "execute_workflow_background", execute)

    await workflow_module.submit_background_with_mapping(
        parsed,
        flow,
        user,
        stream_protocol="langflow",
    )

    assert execute.call_args.kwargs["parsed"].data == sanitized
    assert parsed.data["nodes"][0]["data"]["source"] == "request"
