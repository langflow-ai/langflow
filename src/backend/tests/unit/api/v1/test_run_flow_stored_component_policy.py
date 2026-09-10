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


def _advanced_flow(user_id, data: dict):
    """The advanced-run path reads authorization fields the simple-run helper omits."""
    flow = _make_flow(user_id, data)
    flow.workspace_id = None
    flow.folder_id = None
    return flow


def _advanced_run_env(monkeypatch, *, cached_graph, admin_only: bool):
    """Wire the advanced-run seam so only the cached-graph policy decision is exercised."""
    from langflow.api.v1 import endpoints

    captured: dict = {}

    def fake_from_payload(data, **_kwargs):
        rebuilt = SimpleNamespace(run_id=None, rebuilt=True)
        captured["rebuilt_from_payload"] = data
        return rebuilt

    async def fake_run_graph_internal(**kwargs):
        captured["runtime_graph"] = kwargs["graph"]
        return [], "session"

    monkeypatch.setattr(endpoints.Graph, "from_payload", fake_from_payload)
    monkeypatch.setattr(endpoints, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(endpoints, "run_graph_internal", fake_run_graph_internal)
    monkeypatch.setattr(endpoints, "get_task_service", lambda: SimpleNamespace(fire_and_forget_task=AsyncMock()))
    monkeypatch.setattr(endpoints, "get_memory_base_service", lambda: SimpleNamespace(on_flow_output=Mock()))
    monkeypatch.setattr(endpoints, "process_tweaks", lambda graph_data, _tweaks, **_kwargs: graph_data)
    monkeypatch.setattr(endpoints, "raise_if_hitl_unsupported", lambda _graph_data: None)
    monkeypatch.setattr(
        endpoints,
        "get_session_service",
        lambda: SimpleNamespace(load_session=AsyncMock(return_value=(cached_graph, None))),
    )
    # The cached graph belongs to this same caller, so the existing principal check keeps it.
    monkeypatch.setattr(endpoints, "_graph_executes_as_actor", lambda *_a, **_k: True)
    monkeypatch.setattr(endpoints, "admin_only_build_required", lambda *, is_superuser: admin_only)  # noqa: ARG005

    sanitized = _stored_graph("# server-trusted source")
    policy = AsyncMock(return_value=sanitized if admin_only else None)
    monkeypatch.setattr(endpoints, "prepare_flow_build_for_user", policy)

    return endpoints, captured, policy


@pytest.mark.asyncio
async def test_cached_advanced_run_graph_is_rebuilt_when_admin_only_applies(monkeypatch):
    """A graph cached before admin-only mode was enabled must not be reused.

    Session cache keys carry no policy generation, so a graph compiled while the policy was
    off still embeds the caller's own component source. Reusing it would execute that source
    unchecked, which is the same persistence bypass this PR closes for stored flow data.
    """
    caller_id = uuid4()
    cached = SimpleNamespace(run_id=None, rebuilt=False)
    endpoints, captured, policy = _advanced_run_env(monkeypatch, cached_graph=cached, admin_only=True)
    flow = _advanced_flow(caller_id, _stored_graph("import os\n_x = os.system('id')\n"))

    await endpoints.experimental_run_flow(
        session=SimpleNamespace(exec=AsyncMock(), in_transaction=lambda: False, commit=AsyncMock()),
        flow=flow,
        inputs=None,
        outputs=None,
        tweaks=None,
        stream=False,
        session_id="cached-session",
        api_key_user=SimpleNamespace(id=caller_id, is_superuser=False),
    )

    policy.assert_awaited_once()
    assert captured["runtime_graph"] is not cached, "the pre-policy cached graph was executed"
    assert captured["runtime_graph"].rebuilt is True
    assert captured["rebuilt_from_payload"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == (
        "# server-trusted source"
    )


@pytest.mark.asyncio
async def test_cached_advanced_run_graph_is_reused_when_the_policy_is_off(monkeypatch):
    """With admin-only mode off the rebuild would not sanitize, so the cache stays a fast path."""
    caller_id = uuid4()
    cached = SimpleNamespace(run_id=None, rebuilt=False)
    endpoints, captured, _policy = _advanced_run_env(monkeypatch, cached_graph=cached, admin_only=False)
    flow = _advanced_flow(caller_id, _stored_graph("# anything"))

    await endpoints.experimental_run_flow(
        session=SimpleNamespace(exec=AsyncMock(), in_transaction=lambda: False, commit=AsyncMock()),
        flow=flow,
        inputs=None,
        outputs=None,
        tweaks=None,
        stream=False,
        session_id="cached-session",
        api_key_user=SimpleNamespace(id=caller_id, is_superuser=False),
    )

    assert captured["runtime_graph"] is cached
    assert "rebuilt_from_payload" not in captured
