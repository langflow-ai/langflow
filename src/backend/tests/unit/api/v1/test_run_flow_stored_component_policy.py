"""Regressions for the caller-aware component policy on the stored-graph run path.

``simple_run_flow`` backs ``POST /run/{flow}``, ``POST /run/session/{flow}``,
``POST /webhook/{flow}``, the MCP ``tools/call`` handler and the OpenAI Responses
API. All of them execute the graph persisted on the flow row, which any user who
can write a flow controls. Before this gate the stored bytes reached
``Graph.from_payload`` with only the caller-agnostic global validator applied, so
``custom_component_admin_only`` was enforced on inline build payloads but not on
stored ones.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException


def _stored_graph(source: str) -> dict:
    return {
        "nodes": [
            {
                "id": "ChatInput-1",
                "data": {
                    "id": "ChatInput-1",
                    "type": "ChatInput",
                    "node": {"template": {"code": {"value": source}}},
                },
            }
        ],
        "edges": [],
    }


def _make_flow(user_id, data: dict):
    from datetime import datetime, timezone

    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        name="stored",
        data=data,
        updated_at=datetime(2026, 8, 5, 12, tzinfo=timezone.utc),
    )


@pytest.fixture
def run_flow_env(monkeypatch):
    """Neutralize the surrounding run machinery so only the policy seam is exercised."""
    from langflow.api.v1 import endpoints

    job_service = SimpleNamespace(
        create_job=AsyncMock(),
        execute_with_status=AsyncMock(return_value=([], "session")),
    )
    monkeypatch.setattr(endpoints, "get_job_service", lambda: job_service)
    monkeypatch.setattr(
        endpoints,
        "get_task_service",
        lambda: SimpleNamespace(fire_and_forget_task=AsyncMock()),
    )
    monkeypatch.setattr(endpoints, "get_memory_base_service", lambda: SimpleNamespace(on_flow_output=AsyncMock()))
    monkeypatch.setattr(endpoints, "process_tweaks", lambda graph_data, _tweaks, **_kwargs: graph_data)
    monkeypatch.setattr(endpoints, "raise_if_hitl_unsupported", lambda _graph_data: None)
    monkeypatch.setattr(endpoints, "apply_global_variable_defaults", AsyncMock(side_effect=lambda data, _uid: data))
    return endpoints


@pytest.mark.asyncio
async def test_stored_graph_policy_denial_stops_the_run(run_flow_env, monkeypatch):
    """A policy rejection on the stored graph must abort before any graph is built."""
    from langflow.api.v1.schemas import SimplifiedAPIRequest
    from lfx.utils.flow_validation import CustomComponentValidationError

    endpoints = run_flow_env
    user_id = uuid4()
    flow = _make_flow(user_id, _stored_graph("# attacker source"))
    seen: dict = {}

    async def reject(data, *, is_superuser):
        seen["validated"] = data
        assert is_superuser is False
        message = "custom components are restricted to administrators"
        raise CustomComponentValidationError(message)

    from_payload = Mock(side_effect=AssertionError("graph must not be built"))
    monkeypatch.setattr(endpoints, "prepare_flow_build_for_user", reject)
    monkeypatch.setattr(endpoints.Graph, "from_payload", from_payload)

    with pytest.raises(CustomComponentValidationError, match="restricted to administrators"):
        await endpoints.simple_run_flow(
            flow=flow,
            input_request=SimplifiedAPIRequest(session_id="s"),
            api_key_user=SimpleNamespace(id=user_id, is_superuser=False),
        )

    assert seen["validated"] == flow.data
    from_payload.assert_not_called()


@pytest.mark.asyncio
async def test_cached_session_graph_is_refused_when_admin_only_applies(monkeypatch):
    """A session's cached graph predates the policy, so it must not execute under admin-only.

    Session cache keys carry no policy generation: a graph cached while admin-only mode was
    off still embeds the caller's own component source. 1.12 rebuilds from stored data at this
    point; this branch has no rebuild path, so it refuses instead of executing.
    """
    from langflow.api.v1 import endpoints

    caller = SimpleNamespace(id=uuid4(), is_superuser=False)
    flow = _make_flow(caller.id, _stored_graph("# stored source"))
    # The advanced-run authorization guard reads fields the simple-run helper omits.
    flow.workspace_id = None
    flow.folder_id = None
    cached_graph = SimpleNamespace(run_id=None)

    monkeypatch.setattr(endpoints, "admin_only_build_required", lambda *, is_superuser: True)  # noqa: ARG005
    monkeypatch.setattr(
        endpoints,
        "get_session_service",
        lambda: SimpleNamespace(load_session=AsyncMock(return_value=(cached_graph, None))),
        raising=False,
    )
    monkeypatch.setattr(endpoints, "ensure_flow_permission", AsyncMock(), raising=False)

    with pytest.raises(HTTPException) as exc_info:
        await endpoints.experimental_run_flow(
            session=SimpleNamespace(exec=AsyncMock(), in_transaction=lambda: False, commit=AsyncMock()),
            flow=flow,
            inputs=None,
            outputs=None,
            tweaks=None,
            stream=False,
            session_id="cached-session",
            api_key_user=caller,
        )

    assert exc_info.value.status_code == 400
    assert "predates the admin-only component policy" in str(exc_info.value.detail)
