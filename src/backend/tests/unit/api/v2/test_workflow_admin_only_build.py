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
