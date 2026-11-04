"""MCP argument preprocessing must not run stored code before the build policy."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import langflow
import pytest
from langflow.api.v1 import endpoints, mcp_utils
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_settings_service
from lfx.utils import flow_validation


@pytest.fixture
def stored_custom_flow(tmp_path):
    """Keep a real input node whose modified source has an observable import-time effect."""
    starter = Path(langflow.__file__).parent / "initial_setup" / "starter_projects" / "Basic Prompting.json"
    data = json.loads(starter.read_text(encoding="utf-8"))["data"]
    node = next(node for node in data["nodes"] if node["data"]["type"] == "ChatInput")
    original_source = node["data"]["node"]["template"]["code"]["value"]
    marker = tmp_path / "stored-code-executed"
    node["data"]["node"]["template"]["code"]["value"] = (
        f"_MCP_CALL_PROBE = __import__('pathlib').Path({str(marker)!r}).write_text('executed')\n" + original_source
    )
    # An advertised argument forces get_flow_input_tweaks to inspect this node, just as
    # an unknown extra argument does. Keep it visible to check ordinary tweak mapping too.
    node["data"]["node"]["template"]["sender_name"]["advanced"] = False
    flow = Flow(
        id=uuid4(),
        user_id=uuid4(),
        name="Stored custom flow",
        data={"nodes": [node], "edges": []},
    )
    return flow, marker, original_source


@pytest.fixture
def mcp_call_env(monkeypatch):
    """Stub storage and jobs while retaining real tweak parsing, build policy, and graph building."""
    jobs = SimpleNamespace(create_job=AsyncMock(), execute_with_status=AsyncMock(return_value=([], "session")))
    monkeypatch.setattr(mcp_utils, "with_db_session", lambda operation: operation(None))
    monkeypatch.setattr(mcp_utils, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(mcp_utils.get_mcp_config(), "enable_progress_notifications", False)
    monkeypatch.setattr(endpoints, "try_warm_run_graph", AsyncMock(return_value=None))
    monkeypatch.setattr(endpoints, "apply_global_variable_defaults", AsyncMock(side_effect=lambda data, _user: data))
    monkeypatch.setattr(endpoints, "get_authorized_legacy_flow_ids", AsyncMock(return_value=set()))
    monkeypatch.setattr(endpoints, "get_job_service", lambda: jobs)
    monkeypatch.setattr(endpoints, "get_task_service", lambda: SimpleNamespace(fire_and_forget_task=AsyncMock()))
    monkeypatch.setattr(endpoints, "get_memory_base_service", lambda: SimpleNamespace(on_flow_output=AsyncMock()))
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", True)
    monkeypatch.setattr(settings, "block_code_interpreter_components", False)
    return jobs, settings


async def _call_tool(monkeypatch, flow, arguments, *, is_superuser):
    monkeypatch.setattr(mcp_utils, "get_flow_snake_case", AsyncMock(return_value=flow))
    user = SimpleNamespace(id=flow.user_id, is_superuser=is_superuser)
    tokens = [
        (mcp_utils.current_user_ctx, mcp_utils.current_user_ctx.set(user)),
        (mcp_utils.authenticated_caller_ctx, mcp_utils.authenticated_caller_ctx.set(user.id)),
        (mcp_utils.current_request_variables_ctx, mcp_utils.current_request_variables_ctx.set(None)),
        (mcp_utils.current_request_headers_ctx, mcp_utils.current_request_headers_ctx.set(None)),
    ]
    try:
        return await mcp_utils.handle_call_tool("stored_custom_flow", arguments, SimpleNamespace())
    finally:
        for context, token in reversed(tokens):
            context.reset(token)


@pytest.mark.parametrize("extra_arguments", [{}, {"zz": 1}, {"sender_name": "caller"}])
async def test_mcp_call_rejects_stored_custom_code_without_executing_it(
    monkeypatch, stored_custom_flow, mcp_call_env, extra_arguments
):
    flow, marker, original_source = stored_custom_flow
    jobs, settings = mcp_call_env
    stored_data = copy.deepcopy(flow.data)
    monkeypatch.setattr(settings, "custom_component_admin_only", True)
    monkeypatch.setattr(
        flow_validation,
        "ensure_component_hash_lookups_loaded",
        AsyncMock(return_value={"ChatInput": {flow_validation._compute_code_hash(original_source)}}),
    )

    with pytest.raises(RuntimeError, match="Flow build blocked"):
        await _call_tool(monkeypatch, flow, {"input_value": "hello", **extra_arguments}, is_superuser=False)

    assert not marker.exists()
    jobs.create_job.assert_not_awaited()
    jobs.execute_with_status.assert_not_awaited()
    assert flow.data == stored_data


@pytest.mark.parametrize(("admin_only", "is_superuser"), [(False, False), (True, True)])
async def test_mcp_call_preserves_authorized_custom_code_and_input_tweaks(
    monkeypatch, stored_custom_flow, mcp_call_env, admin_only, is_superuser
):
    flow, marker, _original_source = stored_custom_flow
    jobs, settings = mcp_call_env
    monkeypatch.setattr(settings, "custom_component_admin_only", admin_only)

    result = await _call_tool(
        monkeypatch,
        flow,
        {"input_value": "hello", "sender_name": "caller", "zz": 1},
        is_superuser=is_superuser,
    )

    assert result == []
    assert marker.read_text(encoding="utf-8") == "executed"
    jobs.execute_with_status.assert_awaited_once()
    graph = jobs.execute_with_status.call_args.kwargs["graph"]
    assert graph.vertices[0].params["sender_name"] == "caller"
    assert "zz" not in graph.vertices[0].params
