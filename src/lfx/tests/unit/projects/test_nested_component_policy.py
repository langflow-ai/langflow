"""Reviewed Hook definitions still pass caller-aware policy before every graph build."""

import json
from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from lfx.base.agents.hooks import HookBinding
from lfx.graph.graph.base import Graph
from lfx.projects.baselines import build_slot_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.hooks import HookFlowRunner, hook_outputs
from lfx.utils.flow_validation import CustomComponentValidationError


@asynccontextmanager
async def _authorized_scope(**_kwargs):
    yield


@pytest.fixture
def reviewed_hook(tmp_path, monkeypatch):
    from lfx.base.tools import run_flow as run_flow_module
    from lfx.utils import flow_validation

    flow = build_slot_baseline("builtin:hook")
    flow["id"] = str(uuid4())
    path = tmp_path / "hook.json"
    path.write_text(json.dumps(flow))
    output = hook_outputs(flow["data"])[0]
    binding = HookBinding(
        flow_id=flow["id"],
        node_id=output["node_id"],
        output_name=output["output_name"],
        revision=flow_revision(flow["data"]),
        on_event="before_llm_call",
    )
    parent = SimpleNamespace(context={"project_dir": str(tmp_path)}, run_id=str(uuid4()), session_id=str(uuid4()))
    component = SimpleNamespace(user_id=str(uuid4()), graph=parent, _vertex=SimpleNamespace(graph=parent, data={}))
    identity = AsyncMock(return_value=False)
    guard = AsyncMock(return_value=None)
    monkeypatch.setattr(run_flow_module, "_model_provider_policy", _authorized_scope)
    monkeypatch.setattr(run_flow_module, "get_user_is_superuser", identity)
    monkeypatch.setattr(flow_validation, "custom_component_admin_only_enabled", lambda: True)
    monkeypatch.setattr(flow_validation, "prepare_flow_build_for_user", guard)
    return SimpleNamespace(
        runner=HookFlowRunner(component), binding=binding, flow=flow, path=path, guard=guard, identity=identity
    )


@pytest.mark.parametrize("is_superuser", [False, True])
async def test_reviewed_hook_builds_sanitized_copy_with_caller_identity(reviewed_hook, is_superuser):
    env = reviewed_hook
    env.identity.return_value = is_superuser
    sanitized = deepcopy(env.flow["data"])
    node = next(n for n in sanitized["nodes"] if n["id"] == env.binding.node_id)
    node["data"]["node"]["template"]["reason"]["value"] = "sanitized by policy"
    env.guard.return_value = sanitized

    first = await env.runner(env.binding, {})
    second = await env.runner(env.binding, {})

    assert first.reason == second.reason == "sanitized by policy"
    assert env.identity.await_count == env.guard.await_count == 2
    for call in env.guard.await_args_list:
        assert call.kwargs["is_superuser"] is is_superuser
        assert call.args[0] == env.flow["data"]
    assert json.loads(env.path.read_text()) == env.flow


@pytest.mark.parametrize("cached", [False, True])
async def test_reviewed_hook_policy_denial_prevents_graph_construction(reviewed_hook, monkeypatch, cached):
    env = reviewed_hook
    if cached:
        await env.runner(env.binding, {})
    env.guard.side_effect = CustomComponentValidationError("component policy refused the reviewed flow")
    original = Graph.from_payload

    def reject_runtime_build(*args, **kwargs):
        if kwargs.get("instantiate_components") is not False:
            pytest.fail("The rejected definition reached graph construction")
        return original(*args, **kwargs)

    monkeypatch.setattr(Graph, "from_payload", reject_runtime_build)
    with pytest.raises(CustomComponentValidationError, match="component policy refused"):
        await env.runner(env.binding, {})
