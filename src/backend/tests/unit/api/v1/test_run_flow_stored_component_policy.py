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
async def test_stored_graph_builds_from_the_sanitized_copy(run_flow_env, monkeypatch):
    """The executed payload is the server-trusted copy, not the stored bytes."""
    from langflow.api import warm_graph
    from langflow.api.v1.schemas import SimplifiedAPIRequest

    endpoints = run_flow_env
    user_id = uuid4()
    flow = _make_flow(user_id, _stored_graph("# stored source"))
    sanitized = _stored_graph("# trusted server source")
    captured: dict = {}

    async def sanitize(_data, *, is_superuser):
        assert is_superuser is False
        return sanitized

    def fake_from_payload(payload, **kwargs):  # noqa: ARG001
        captured["payload"] = payload
        graph = SimpleNamespace(vertices=[], run_id=None)
        graph.set_run_id = lambda run_id: setattr(graph, "run_id", str(run_id))
        return graph

    monkeypatch.setattr(endpoints, "prepare_flow_build_for_user", sanitize)
    monkeypatch.setattr(endpoints.Graph, "from_payload", staticmethod(fake_from_payload))
    monkeypatch.setattr(
        warm_graph,
        "warm_deepcopy",
        AsyncMock(side_effect=AssertionError("warm template must be skipped after sanitization")),
    )

    await endpoints.simple_run_flow(
        flow=flow,
        input_request=SimplifiedAPIRequest(session_id="s"),
        api_key_user=SimpleNamespace(id=user_id, is_superuser=False),
    )

    executed = captured["payload"]["nodes"][0]["data"]["node"]["template"]["code"]["value"]
    assert executed == "# trusted server source"
    # The stored row is never rewritten by the sanitizer.
    assert flow.data["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "# stored source"


@pytest.mark.asyncio
async def test_permissive_policy_leaves_the_warm_fast_path_intact(run_flow_env, monkeypatch):
    """With no caller-specific restriction the pre-existing warm fast path still serves."""
    from langflow.api import warm_graph
    from langflow.api.v1.schemas import SimplifiedAPIRequest

    endpoints = run_flow_env
    user_id = uuid4()
    flow = _make_flow(user_id, _stored_graph("# stored source"))
    warm = SimpleNamespace(vertices=[], run_id=None)
    warm.set_run_id = lambda run_id: setattr(warm, "run_id", str(run_id))

    async def permissive(_data, *, is_superuser):
        assert is_superuser is False

    monkeypatch.setattr(endpoints, "prepare_flow_build_for_user", permissive)
    monkeypatch.setattr(warm_graph, "warm_deepcopy", AsyncMock(return_value=warm))
    monkeypatch.setattr(
        endpoints.Graph,
        "from_payload",
        staticmethod(Mock(side_effect=AssertionError("cold path used"))),
    )

    await endpoints.simple_run_flow(
        flow=flow,
        input_request=SimplifiedAPIRequest(session_id="s"),
        api_key_user=SimpleNamespace(id=user_id, is_superuser=False),
    )

    assert warm.run_id is not None


@pytest.mark.asyncio
async def test_superuser_status_is_forwarded_to_the_policy(run_flow_env, monkeypatch):
    """The documented superuser exception must reach the policy from this seam too."""
    from langflow.api import warm_graph
    from langflow.api.v1.schemas import SimplifiedAPIRequest

    endpoints = run_flow_env
    user_id = uuid4()
    flow = _make_flow(user_id, _stored_graph("# admin source"))
    warm = SimpleNamespace(vertices=[], run_id=None)
    warm.set_run_id = lambda run_id: setattr(warm, "run_id", str(run_id))
    seen: dict = {}

    async def record(_data, *, is_superuser):
        seen["is_superuser"] = is_superuser

    monkeypatch.setattr(endpoints, "prepare_flow_build_for_user", record)
    monkeypatch.setattr(warm_graph, "warm_deepcopy", AsyncMock(return_value=warm))

    await endpoints.simple_run_flow(
        flow=flow,
        input_request=SimplifiedAPIRequest(session_id="s"),
        api_key_user=SimpleNamespace(id=user_id, is_superuser=True),
    )

    assert seen["is_superuser"] is True
