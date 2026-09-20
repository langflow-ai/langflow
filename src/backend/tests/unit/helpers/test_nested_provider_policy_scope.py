"""Nested saved-flow execution must use the target flow's provider-policy scope."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from langchain_core.tools import ToolException
from langflow.helpers.flow import generate_function_for_flow, load_flow, run_flow
from langflow.services.database.models import Folder
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope
from lfx.base.tools.flow_tool import FlowTool
from lfx.base.tools.run_flow import RunFlowBaseComponent
from lfx.components.models_and_agents.a2a_agent import A2AAgentComponent
from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.schema.data import Data
from lfx.services.model_provider_policy import (
    BaseModelProviderPolicyService,
    ModelProviderPolicyError,
    ModelProviderPolicyPurpose,
    current_model_provider_policy_context,
    require_model_provider,
    reset_current_model_provider_policy_context,
    set_current_model_provider_policy_context,
)


class _ProjectPolicy(BaseModelProviderPolicyService):
    """Allow providers only in the mutable set of project ids."""

    SNAPSHOT_CACHE_MAX_SIZE = 0

    def __init__(self) -> None:
        super().__init__()
        self.allowed_projects: set[str] = set()
        self.seen_projects: list[str | None] = []
        self.set_ready()

    def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
        assert purpose is ModelProviderPolicyPurpose.USE
        project_id = context.attributes.get("project_id")
        normalized = str(project_id) if project_id is not None else None
        self.seen_projects.append(normalized)
        return candidate_provider_ids if normalized in self.allowed_projects else ()


class _ProviderGraph:
    """Small graph double whose provider use precedes its network-capable action."""

    def __init__(self, *, flow_id: str | None, probe: MagicMock, callback=None) -> None:
        self.flow_id = flow_id
        self.flow_name = None
        self.user_id: str | None = None
        self.run_id = None
        self.session_id = None
        self.vertices = []
        self.successor_map = {}
        self.description = None
        self.updated_at = None
        self._probe = probe
        self._callback = callback

    def set_run_id(self, run_id) -> None:
        self.run_id = run_id

    async def arun(self, *_args, **_kwargs):
        if self._callback is not None:
            return await self._callback()
        require_model_provider(user_id=self.user_id, provider="OpenAI")
        self._probe()
        return []


@pytest.fixture
def project_policy(monkeypatch) -> _ProjectPolicy:
    policy = _ProjectPolicy()
    monkeypatch.setattr("lfx.services.deps.get_model_provider_policy_service", lambda: policy)
    return policy


@pytest.fixture
async def nested_flow_rows(active_user):
    workspaces = [uuid4(), uuid4(), uuid4()]
    async with session_scope() as session:
        projects = [
            Folder(name=f"nested-scope-{index}-{uuid4()}", user_id=active_user.id, workspace_id=workspace_id)
            for index, workspace_id in enumerate(workspaces)
        ]
        session.add_all(projects)
        await session.flush()
        targets = [
            Flow(
                name=f"nested-target-{index}-{uuid4()}",
                data={"nodes": [], "edges": []},
                user_id=active_user.id,
                folder_id=project.id,
                workspace_id=project.workspace_id,
            )
            for index, project in enumerate(projects[1:], start=1)
        ]
        session.add_all(targets)
        await session.flush()
        rows = SimpleNamespace(
            user_id=str(active_user.id),
            outer_project=projects[0].id,
            outer_workspace=projects[0].workspace_id,
            target_project=projects[1].id,
            target_workspace=projects[1].workspace_id,
            target_flow=targets[0].id,
            target_name=targets[0].name,
            moved_project=projects[2].id,
            moved_workspace=projects[2].workspace_id,
            recursive_flow=targets[1].id,
        )
    yield rows

    async with session_scope() as session:
        for flow_id in (rows.target_flow, rows.recursive_flow):
            if flow := await session.get(Flow, flow_id):
                await session.delete(flow)
        for project_id in (rows.outer_project, rows.target_project, rows.moved_project):
            if project := await session.get(Folder, project_id):
                await session.delete(project)


@contextmanager
def _outer_scope(rows):
    token = set_current_model_provider_policy_context(
        user_id=rows.user_id,
        attributes={
            "project_id": rows.outer_project,
            "workspace_id": rows.outer_workspace,
            "provider_scope_required": True,
        },
    )
    try:
        yield
    finally:
        reset_current_model_provider_policy_context(token)


def _install_build_probe(monkeypatch, probe: MagicMock):
    from lfx.graph.graph.base import Graph

    def _from_payload(_payload=None, *, payload=None, flow_id=None, user_id=None, **_kwargs):
        _ = payload
        require_model_provider(user_id=user_id, provider="OpenAI")
        probe()
        return _ProviderGraph(flow_id=str(flow_id) if flow_id is not None else None, probe=probe)

    monkeypatch.setattr(Graph, "from_payload", staticmethod(_from_payload))


@pytest.mark.parametrize("entry", ["loader", "custom", "generated"])
@pytest.mark.asyncio
async def test_cold_nested_entry_denies_target_before_provider_io(entry, nested_flow_rows, project_policy, monkeypatch):
    """An outer grant must not authorize a denied target build or execution."""
    probe = MagicMock()
    _install_build_probe(monkeypatch, probe)
    project_policy.allowed_projects = {str(nested_flow_rows.outer_project)}

    async def _invoke():
        if entry == "loader":
            return await load_flow(nested_flow_rows.user_id, flow_id=str(nested_flow_rows.target_flow))
        if entry == "custom":
            component = SimpleNamespace(
                user_id=UUID(nested_flow_rows.user_id),
                graph=SimpleNamespace(run_id=None),
            )
            return await CustomComponent.run_flow(
                component,
                flow_id=str(nested_flow_rows.target_flow),
                output_type="any",
            )
        function = generate_function_for_flow([], str(nested_flow_rows.target_flow), nested_flow_rows.user_id)
        return await function()

    expected_error = ToolException if entry == "generated" else ModelProviderPolicyError
    with _outer_scope(nested_flow_rows), pytest.raises(expected_error):
        await _invoke()

    probe.assert_not_called()


@pytest.mark.parametrize("entry", ["loader", "custom", "generated"])
@pytest.mark.asyncio
async def test_cold_nested_entry_uses_target_grant_when_outer_is_denied(
    entry, nested_flow_rows, project_policy, monkeypatch
):
    """A target grant must work even when the ambient outer project is denied."""
    probe = MagicMock()
    _install_build_probe(monkeypatch, probe)
    project_policy.allowed_projects = {str(nested_flow_rows.target_project)}

    with _outer_scope(nested_flow_rows):
        if entry == "loader":
            await load_flow(nested_flow_rows.user_id, flow_id=str(nested_flow_rows.target_flow))
        elif entry == "custom":
            component = SimpleNamespace(
                user_id=UUID(nested_flow_rows.user_id),
                graph=SimpleNamespace(run_id=None),
            )
            await CustomComponent.run_flow(
                component,
                flow_id=str(nested_flow_rows.target_flow),
                output_type="any",
            )
        else:
            function = generate_function_for_flow([], str(nested_flow_rows.target_flow), nested_flow_rows.user_id)
            await function()

    assert probe.call_count >= 1
    assert project_policy.seen_projects
    assert set(project_policy.seen_projects) == {str(nested_flow_rows.target_project)}


@pytest.mark.parametrize("entry", ["helper", "flow_tool"])
@pytest.mark.asyncio
async def test_prebuilt_and_flow_tool_reauthorize_in_target_scope(entry, nested_flow_rows, project_policy):
    """A prebuilt/frozen-style graph cannot retain the outer project's grant."""
    probe = MagicMock()
    graph = _ProviderGraph(flow_id=str(nested_flow_rows.target_flow), probe=probe)
    project_policy.allowed_projects = {str(nested_flow_rows.outer_project)}

    async def _invoke():
        if entry == "helper":
            return await run_flow(
                graph=graph,
                flow_id=str(nested_flow_rows.target_flow),
                user_id=nested_flow_rows.user_id,
                output_type="any",
            )
        tool = FlowTool.model_construct(
            name="nested_target",
            description="nested target",
            graph=graph,
            flow_id=str(nested_flow_rows.target_flow),
            user_id=nested_flow_rows.user_id,
            inputs=[],
            session_id=None,
            get_final_results_only=True,
        )
        return await tool._arun()

    with _outer_scope(nested_flow_rows), pytest.raises(ModelProviderPolicyError):
        await _invoke()

    probe.assert_not_called()


@pytest.mark.asyncio
async def test_internal_a2a_builds_and_runs_under_target_scope(nested_flow_rows, project_policy, monkeypatch):
    """Internal A2A cannot construct its target graph in the ambient caller domain."""
    probe = MagicMock()
    _install_build_probe(monkeypatch, probe)
    project_policy.allowed_projects = {str(nested_flow_rows.outer_project)}
    published = Data(
        data={
            "id": str(nested_flow_rows.target_flow),
            "name": nested_flow_rows.target_name,
            "updated_at": None,
        }
    )
    component = A2AAgentComponent(
        mode="Internal",
        agent_name_selected=nested_flow_rows.target_name,
        input_value="hello",
    )
    component._user_id = UUID(nested_flow_rows.user_id)
    component._frontend_node_flow_id = str(nested_flow_rows.target_flow)
    selected = component._inputs["agent_name_selected"]
    selected.options = [nested_flow_rows.target_name]
    selected.options_metadata = [{"id": str(nested_flow_rows.target_flow)}]
    monkeypatch.setattr(component, "alist_a2a_agents_by_flow_folder", AsyncMock(return_value=[published]))

    with _outer_scope(nested_flow_rows), pytest.raises(ModelProviderPolicyError):
        await component.send_to_agent()

    probe.assert_not_called()


@pytest.mark.asyncio
async def test_cached_run_flow_reconstruction_uses_fresh_target_scope(nested_flow_rows, project_policy, monkeypatch):
    """Shared Run Flow cache hydration must not build under the caller's domain."""
    probe = MagicMock()
    _install_build_probe(monkeypatch, probe)
    project_policy.allowed_projects = {str(nested_flow_rows.outer_project)}
    updated_at = "2026-08-27T00:00:00Z"
    cache_entry = {
        "graph_dump": {"data": {"nodes": [], "edges": []}},
        "flow_id": str(nested_flow_rows.target_flow),
        "user_id": nested_flow_rows.user_id,
        "updated_at": updated_at,
    }
    component = RunFlowBaseComponent()
    component._user_id = nested_flow_rows.user_id
    component.cache_flow = True
    component._shared_component_cache = MagicMock()
    component._shared_component_cache.get.return_value = cache_entry

    with _outer_scope(nested_flow_rows), pytest.raises(ModelProviderPolicyError):
        await component.get_graph(
            flow_id_selected=str(nested_flow_rows.target_flow),
            updated_at=updated_at,
        )

    probe.assert_not_called()


@pytest.mark.asyncio
async def test_cached_graph_rechecks_revocation_on_every_execution(nested_flow_rows, project_policy):
    probe = MagicMock()
    graph = _ProviderGraph(flow_id=str(nested_flow_rows.target_flow), probe=probe)
    project_policy.allowed_projects = {
        str(nested_flow_rows.outer_project),
        str(nested_flow_rows.target_project),
    }

    with _outer_scope(nested_flow_rows):
        await run_flow(graph=graph, flow_id=str(nested_flow_rows.target_flow), user_id=nested_flow_rows.user_id)
        project_policy.allowed_projects = {str(nested_flow_rows.outer_project)}
        with pytest.raises(ModelProviderPolicyError):
            await run_flow(graph=graph, flow_id=str(nested_flow_rows.target_flow), user_id=nested_flow_rows.user_id)

    assert probe.call_count == 1
    assert project_policy.seen_projects[-1] == str(nested_flow_rows.target_project)


@pytest.mark.asyncio
async def test_cached_graph_rechecks_target_project_after_move(nested_flow_rows, project_policy):
    probe = MagicMock()
    graph = _ProviderGraph(flow_id=str(nested_flow_rows.target_flow), probe=probe)
    project_policy.allowed_projects = {
        str(nested_flow_rows.outer_project),
        str(nested_flow_rows.target_project),
    }

    with _outer_scope(nested_flow_rows):
        await run_flow(graph=graph, flow_id=str(nested_flow_rows.target_flow), user_id=nested_flow_rows.user_id)
        async with session_scope() as session:
            target = await session.get(Flow, nested_flow_rows.target_flow)
            target.folder_id = nested_flow_rows.moved_project
            target.workspace_id = nested_flow_rows.moved_workspace
            session.add(target)
        with pytest.raises(ModelProviderPolicyError):
            await run_flow(graph=graph, flow_id=str(nested_flow_rows.target_flow), user_id=nested_flow_rows.user_id)

    assert probe.call_count == 1
    assert project_policy.seen_projects[-1] == str(nested_flow_rows.moved_project)


@pytest.mark.asyncio
async def test_recursive_nested_scope_restores_parent_and_root(nested_flow_rows, project_policy):
    seen: list[tuple[str, str | None]] = []

    def _project() -> str | None:
        context = current_model_provider_policy_context()
        value = context.attributes.get("project_id") if context is not None else None
        return str(value) if value is not None else None

    async def _inner():
        seen.append(("inner", _project()))
        return []

    inner_graph = _ProviderGraph(
        flow_id=str(nested_flow_rows.recursive_flow),
        probe=MagicMock(),
        callback=_inner,
    )

    async def _outer():
        seen.append(("parent-before", _project()))
        await run_flow(
            graph=inner_graph,
            flow_id=str(nested_flow_rows.recursive_flow),
            user_id=nested_flow_rows.user_id,
        )
        seen.append(("parent-after", _project()))
        return []

    outer_graph = _ProviderGraph(
        flow_id=str(nested_flow_rows.target_flow),
        probe=MagicMock(),
        callback=_outer,
    )
    project_policy.allowed_projects = {
        str(nested_flow_rows.outer_project),
        str(nested_flow_rows.target_project),
        str(nested_flow_rows.moved_project),
    }

    with _outer_scope(nested_flow_rows):
        await run_flow(
            graph=outer_graph,
            flow_id=str(nested_flow_rows.target_flow),
            user_id=nested_flow_rows.user_id,
        )
        seen.append(("root", _project()))

    assert seen == [
        ("parent-before", str(nested_flow_rows.target_project)),
        ("inner", str(nested_flow_rows.moved_project)),
        ("parent-after", str(nested_flow_rows.target_project)),
        ("root", str(nested_flow_rows.outer_project)),
    ]


@pytest.mark.asyncio
async def test_nested_scope_restores_parent_after_child_exception(nested_flow_rows, project_policy):
    error_message = "child failed"

    async def _raise():
        context = current_model_provider_policy_context()
        assert str(context.attributes["project_id"]) == str(nested_flow_rows.target_project)
        raise RuntimeError(error_message)

    graph = _ProviderGraph(flow_id=str(nested_flow_rows.target_flow), probe=MagicMock(), callback=_raise)
    project_policy.allowed_projects = {str(nested_flow_rows.target_project)}

    with _outer_scope(nested_flow_rows):
        with pytest.raises(RuntimeError, match=error_message):
            await run_flow(graph=graph, flow_id=str(nested_flow_rows.target_flow), user_id=nested_flow_rows.user_id)
        context = current_model_provider_policy_context()
        assert str(context.attributes["project_id"]) == str(nested_flow_rows.outer_project)


@pytest.mark.asyncio
async def test_concurrent_nested_runs_keep_target_scopes_isolated(nested_flow_rows, project_policy):
    ready = asyncio.Event()
    entered = 0
    seen: dict[str, list[str]] = {"first": [], "second": []}

    def _callback(label, expected):
        async def _run():
            nonlocal entered
            context = current_model_provider_policy_context()
            seen[label].append(str(context.attributes["project_id"]))
            entered += 1
            if entered == 2:
                ready.set()
            await asyncio.wait_for(ready.wait(), timeout=5)
            context = current_model_provider_policy_context()
            seen[label].append(str(context.attributes["project_id"]))
            assert seen[label] == [str(expected), str(expected)]
            return []

        return _run

    first = _ProviderGraph(
        flow_id=str(nested_flow_rows.target_flow),
        probe=MagicMock(),
        callback=_callback("first", nested_flow_rows.target_project),
    )
    second = _ProviderGraph(
        flow_id=str(nested_flow_rows.recursive_flow),
        probe=MagicMock(),
        callback=_callback("second", nested_flow_rows.moved_project),
    )
    project_policy.allowed_projects = {
        str(nested_flow_rows.target_project),
        str(nested_flow_rows.moved_project),
    }

    with _outer_scope(nested_flow_rows):
        await asyncio.gather(
            run_flow(graph=first, flow_id=str(nested_flow_rows.target_flow), user_id=nested_flow_rows.user_id),
            run_flow(graph=second, flow_id=str(nested_flow_rows.recursive_flow), user_id=nested_flow_rows.user_id),
        )
        context = current_model_provider_policy_context()
        assert str(context.attributes["project_id"]) == str(nested_flow_rows.outer_project)


@pytest.mark.parametrize("flow_id", [None, "not-a-uuid"])
@pytest.mark.asyncio
async def test_prebuilt_graph_missing_or_invalid_target_fails_before_execution(
    flow_id, nested_flow_rows, project_policy
):
    probe = MagicMock()
    graph = _ProviderGraph(flow_id=flow_id, probe=probe)
    project_policy.allowed_projects = {str(nested_flow_rows.outer_project)}

    with _outer_scope(nested_flow_rows), pytest.raises((ValueError, TypeError)):
        await run_flow(graph=graph, flow_id=flow_id, user_id=nested_flow_rows.user_id)

    probe.assert_not_called()
