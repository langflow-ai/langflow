"""Regressions for the caller-aware component policy on the nested Run Flow path.

H1-3979311 / LE-2543: with ``LANGFLOW_CUSTOM_COMPONENT_ADMIN_ONLY=true`` a regular
user is refused at ``POST /custom_component`` (403) and at direct stored-flow
execution (400), but the trusted Run Flow component passed the stored child flow's
payload straight to ``Graph.from_payload`` without ``prepare_flow_build_for_user``,
so the child's Python executed inside the server process. These tests pin the
policy gate on ``RunFlowBaseComponent.get_graph``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest
from lfx.base.tools.run_flow import RunFlowBaseComponent
from lfx.graph.graph.base import Graph
from lfx.projects.tool_packs import ToolExport, ToolPackReference, ToolPackToolBinding
from lfx.schema.data import Data
from lfx.utils.flow_validation import CustomComponentValidationError

CALLER_AUTHORED_SOURCE = """\
from lfx.custom import Component
from lfx.schema import Data


class Le2543Probe(Component):
    display_name = "LE2543 Probe"
    outputs = []

    def run_probe(self) -> Data:
        return Data(data={"marker": "OWN_CODE_RAN"})
"""


def _child_flow_data(source: str) -> Data:
    return Data(
        data={
            "data": {
                "nodes": [
                    {
                        "id": "CustomComponent-1",
                        "data": {
                            "id": "CustomComponent-1",
                            "type": "CustomComponent",
                            "node": {"template": {"code": {"value": source}}},
                        },
                    }
                ],
                "edges": [],
            },
            "description": "child flow",
        }
    )


def _child_flow_payload() -> dict:
    """A persistable flow whose component source is the caller's own, matching no registry hash."""
    node_id = "LE2543Probe-1"
    return {
        "name": f"le2543-child-{uuid4().hex[:8]}",
        "description": "regression fixture",
        "data": {
            "nodes": [
                {
                    "id": node_id,
                    "type": "genericNode",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "id": node_id,
                        "type": "CustomComponent",
                        "node": {
                            "base_classes": ["Data"],
                            "display_name": "LE2543 Probe",
                            "template": {
                                "_type": "Component",
                                "code": {"type": "code", "name": "code", "value": CALLER_AUTHORED_SOURCE, "show": True},
                            },
                        },
                    },
                }
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }


@asynccontextmanager
async def _authorized_target_scope(**_kwargs):
    """Unit-test seam; target-scope behavior has dedicated DB-backed coverage."""
    yield


@pytest.fixture
def nested_env(monkeypatch):
    """Neutralize the seams around the policy so only the policy wiring is exercised."""
    from lfx.base.tools import run_flow as run_flow_module

    env = SimpleNamespace(
        get_user_is_superuser=AsyncMock(return_value=False),
        admin_only_build_required=Mock(return_value=False),
        custom_component_admin_only_enabled=Mock(return_value=None),
    )
    monkeypatch.setattr(
        run_flow_module,
        "_model_provider_policy",
        _authorized_target_scope,
    )
    monkeypatch.setattr(run_flow_module, "get_user_is_superuser", env.get_user_is_superuser)
    monkeypatch.setattr(run_flow_module, "admin_only_build_required", env.admin_only_build_required)
    monkeypatch.setattr(
        run_flow_module,
        "custom_component_admin_only_enabled",
        env.custom_component_admin_only_enabled,
    )
    return env


def _component(*, cache_flow: bool = False) -> RunFlowBaseComponent:
    component = RunFlowBaseComponent()
    component._user_id = str(uuid4())
    component.cache_flow = cache_flow
    return component


async def test_get_graph_builds_from_the_sanitized_child_payload(nested_env, monkeypatch):  # noqa: ARG001
    """The nested graph is built from the policy's trusted copy, not the stored bytes."""
    from lfx.base.tools import run_flow as run_flow_module

    component = _component()
    child = _child_flow_data("# caller-authored source")
    sanitized_payload = {"nodes": [], "edges": []}
    captured: dict = {}

    prepare = AsyncMock(return_value=sanitized_payload)
    mock_graph = MagicMock(spec=Graph)

    def fake_from_payload(**kwargs):
        captured["payload"] = kwargs["payload"]
        return mock_graph

    monkeypatch.setattr(run_flow_module, "prepare_flow_build_for_user", prepare)
    monkeypatch.setattr(run_flow_module.Graph, "from_payload", fake_from_payload)
    monkeypatch.setattr(component, "get_flow", AsyncMock(return_value=child))

    result = await component.get_graph(flow_id_selected=str(uuid4()))

    assert result is mock_graph
    prepare.assert_awaited_once()
    assert prepare.await_args.kwargs["is_superuser"] is False
    assert prepare.await_args.args[0]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == (
        "# caller-authored source"
    )
    # The executed payload is the server-trusted copy.
    assert captured["payload"] is sanitized_payload
    # The stored flow data is never rewritten by the sanitizer.
    assert child.data["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "# caller-authored source"


async def test_get_graph_policy_denial_stops_graph_construction(nested_env, monkeypatch):  # noqa: ARG001
    """A policy rejection on the child payload must abort before any graph is built."""
    from lfx.base.tools import run_flow as run_flow_module

    component = _component()
    prepare = AsyncMock(
        side_effect=CustomComponentValidationError("custom components are restricted to administrators")
    )
    from_payload = Mock(side_effect=AssertionError("graph must not be built"))

    monkeypatch.setattr(run_flow_module, "prepare_flow_build_for_user", prepare)
    monkeypatch.setattr(run_flow_module.Graph, "from_payload", from_payload)
    monkeypatch.setattr(component, "get_flow", AsyncMock(return_value=_child_flow_data("# caller-authored source")))

    with pytest.raises(CustomComponentValidationError, match="restricted to administrators"):
        await component.get_graph(flow_id_selected=str(uuid4()))

    prepare.assert_awaited_once()
    from_payload.assert_not_called()


async def test_get_graph_forwards_the_callers_superuser_status(nested_env, monkeypatch):
    """The documented superuser exception must reach the policy from this seam too."""
    from lfx.base.tools import run_flow as run_flow_module

    nested_env.get_user_is_superuser.return_value = True
    component = _component()
    prepare = AsyncMock(return_value=None)

    monkeypatch.setattr(run_flow_module, "prepare_flow_build_for_user", prepare)
    monkeypatch.setattr(run_flow_module.Graph, "from_payload", lambda **_kwargs: MagicMock(spec=Graph))
    monkeypatch.setattr(component, "get_flow", AsyncMock(return_value=_child_flow_data("# admin source")))

    await component.get_graph(flow_id_selected=str(uuid4()))

    assert prepare.await_args.kwargs["is_superuser"] is True


async def test_get_graph_skips_the_flow_cache_when_admin_only_applies(nested_env, monkeypatch):
    """A cached graph carries no policy generation, so admin-only callers never reuse it.

    A graph cached while the policy was off (or before this gate existed) embeds the
    caller's own component source; serving it would bypass the sanitizer.
    """
    from lfx.base.tools import run_flow as run_flow_module

    nested_env.admin_only_build_required.return_value = True
    component = _component(cache_flow=True)
    cache_calls = Mock(side_effect=AssertionError("cache must not be touched under admin-only"))
    prepare = AsyncMock(return_value=None)

    monkeypatch.setattr(component, "_flow_cache_call", cache_calls)
    monkeypatch.setattr(run_flow_module, "prepare_flow_build_for_user", prepare)
    monkeypatch.setattr(run_flow_module.Graph, "from_payload", lambda **_kwargs: MagicMock(spec=Graph))
    monkeypatch.setattr(component, "get_flow", AsyncMock(return_value=_child_flow_data("# caller-authored source")))

    result = await component.get_graph(flow_id_selected=str(uuid4()))

    assert result is not None
    cache_calls.assert_not_called()
    prepare.assert_awaited_once()


async def test_get_graph_skips_the_user_lookup_when_admin_only_is_configured_off(nested_env, monkeypatch):
    """With the policy off, the caller's superuser flag cannot change any outcome.

    Resolving it costs one database user lookup per retrieval, cache hits included,
    so get_graph must consult the flow cache without touching the user table.
    """
    from lfx.base.tools import run_flow as run_flow_module

    nested_env.custom_component_admin_only_enabled.return_value = False
    component = _component(cache_flow=True)
    prepare = AsyncMock(return_value=None)

    monkeypatch.setattr(run_flow_module, "prepare_flow_build_for_user", prepare)
    monkeypatch.setattr(run_flow_module.Graph, "from_payload", lambda **_kwargs: MagicMock(spec=Graph))
    monkeypatch.setattr(component, "get_flow", AsyncMock(return_value=_child_flow_data("# caller-authored source")))

    result = await component.get_graph(flow_id_selected=str(uuid4()))

    assert result is not None
    nested_env.get_user_is_superuser.assert_not_awaited()
    nested_env.admin_only_build_required.assert_not_called()
    prepare.assert_awaited_once()
    assert prepare.await_args.kwargs["is_superuser"] is False


async def test_run_flow_with_cached_graph_surfaces_policy_rejection_verbatim(nested_env, monkeypatch):  # noqa: ARG001
    """The policy refusal must not collapse into a generic ``RuntimeError``.

    The API layer maps ``CustomComponentValidationError`` to HTTP 400, matching the
    direct-execution control; wrapping it would hide the reason and the status.
    """
    component = _component()
    component.flow_name_selected = "child"
    component.flow_id_selected = str(uuid4())
    component.session_id = "s1"
    denial = CustomComponentValidationError("custom components are restricted to administrators")

    monkeypatch.setattr(component, "get_graph", AsyncMock(side_effect=denial))

    with pytest.raises(CustomComponentValidationError) as excinfo:
        await component._run_flow_with_cached_graph(user_id="u1")

    assert excinfo.value is denial


@pytest.mark.security
async def test_real_policy_denies_regular_user_nested_run_flow_load(
    client, active_user, logged_in_headers, monkeypatch
):
    """End-to-end with the REAL policy: no stand-in for prepare_flow_build_for_user.

    The mocked tests above prove the seam honours the policy's outcomes; this one
    runs the real policy so a regression INSIDE it cannot pass unnoticed. Before
    this fix the nested load returned a graph built from the caller's own source.
    """
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "custom_component_admin_only", True)
    monkeypatch.setattr(settings, "allow_custom_components", True)

    created = await client.post("api/v1/flows/", json=_child_flow_payload(), headers=logged_in_headers)
    assert created.status_code == 201
    child_id = created.json()["id"]

    component = RunFlowBaseComponent()
    component._user_id = str(active_user.id)
    component.cache_flow = False

    with pytest.raises(CustomComponentValidationError):
        await component.get_graph(flow_id_selected=child_id)

    await client.delete(f"api/v1/flows/{child_id}", headers=logged_in_headers)


@pytest.mark.security
async def test_real_policy_lets_superuser_load_the_same_child_through_run_flow(
    client, active_super_user, logged_in_headers_super_user, monkeypatch
):
    """The contrast that makes the denial meaningful: the gate is caller-aware.

    If an admin were refused too, the change would be a blanket outage rather than
    a policy, and the test above would pass for the wrong reason. Everything up to
    graph construction is real (settings, DB rows, target resolution, the policy);
    only the constructor is stubbed, since this minimal fixture payload is not a
    fully buildable graph.
    """
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "custom_component_admin_only", True)
    monkeypatch.setattr(settings, "allow_custom_components", True)

    created = await client.post("api/v1/flows/", json=_child_flow_payload(), headers=logged_in_headers_super_user)
    assert created.status_code == 201
    child_id = created.json()["id"]

    captured: dict = {}

    def fake_from_payload(**kwargs):
        captured["payload"] = kwargs["payload"]
        return MagicMock(spec=Graph)

    monkeypatch.setattr(Graph, "from_payload", fake_from_payload)

    component = RunFlowBaseComponent()
    component._user_id = str(active_super_user.id)
    component.cache_flow = False

    graph = await component.get_graph(flow_id_selected=child_id)

    assert graph is not None
    # The superuser's stored source reaches the graph constructor unsanitized.
    nodes = captured["payload"]["nodes"]
    assert nodes[0]["data"]["node"]["template"]["code"]["value"] == CALLER_AUTHORED_SOURCE

    await client.delete(f"api/v1/flows/{child_id}", headers=logged_in_headers_super_user)


@pytest.mark.parametrize("is_superuser", [False, True])
async def test_tool_pack_rechecks_policy_on_cached_definition(nested_env, monkeypatch, is_superuser):
    from lfx.base.tools import run_flow as run_flow_module

    nested_env.get_user_is_superuser.return_value = is_superuser
    component = _component()
    parent = Graph()
    parent.set_run_id()
    component._vertex = SimpleNamespace(graph=parent, data={})
    binding = ToolPackToolBinding(
        reference=ToolPackReference(project_id=uuid4(), revision="a" * 64),
        tool=ToolExport(flow_id=uuid4(), name="Reviewed tool", revision="b" * 64),
        version_id=uuid4(),
    )
    source = _child_flow_data("# reviewed caller source")
    original = deepcopy(source.data)
    loader = AsyncMock(return_value=source)
    prepared = {"nodes": [], "edges": []}
    prepare = AsyncMock(return_value=prepared)
    first, second = MagicMock(spec=Graph), MagicMock(spec=Graph)
    constructor = Mock(side_effect=[first, second])
    monkeypatch.setattr(component, "_tool_pack_binding", lambda: binding)
    monkeypatch.setattr(run_flow_module, "get_tool_pack_flow", loader)
    monkeypatch.setattr(run_flow_module, "prepare_flow_build_for_user", prepare)
    monkeypatch.setattr(run_flow_module.Graph, "from_payload", constructor)

    assert await component.get_graph(flow_id_selected=binding.tool.flow_id) is first
    assert await component.get_graph(flow_id_selected=binding.tool.flow_id) is second

    loader.assert_awaited_once_with(user_id=component.user_id, binding=binding)
    assert prepare.await_count == 2
    for call in prepare.await_args_list:
        assert call.args[0] == original["data"]
        assert call.kwargs["is_superuser"] is is_superuser
    assert all(call.kwargs["payload"] is prepared for call in constructor.call_args_list)
    assert source.data == original
    assert component._pack_snapshot == original


@pytest.mark.parametrize("warm_definition", [False, True])
async def test_tool_pack_policy_denial_stops_graph_construction(nested_env, monkeypatch, warm_definition):  # noqa: ARG001
    from lfx.base.tools import run_flow as run_flow_module

    component = _component()
    parent = Graph()
    parent.set_run_id()
    component._vertex = SimpleNamespace(graph=parent, data={})
    binding = ToolPackToolBinding(
        reference=ToolPackReference(project_id=uuid4(), revision="a" * 64),
        tool=ToolExport(flow_id=uuid4(), name="Reviewed tool", revision="b" * 64),
        version_id=uuid4(),
    )
    loader = AsyncMock(return_value=_child_flow_data("# reviewed caller source"))
    prepare = AsyncMock(return_value=None)
    constructor = Mock(return_value=MagicMock(spec=Graph))
    monkeypatch.setattr(component, "_tool_pack_binding", lambda: binding)
    monkeypatch.setattr(run_flow_module, "get_tool_pack_flow", loader)
    monkeypatch.setattr(run_flow_module, "prepare_flow_build_for_user", prepare)
    monkeypatch.setattr(run_flow_module.Graph, "from_payload", constructor)
    if warm_definition:
        await component.get_graph(flow_id_selected=binding.tool.flow_id)
        constructor.reset_mock()
    prepare.side_effect = CustomComponentValidationError("custom components are restricted to administrators")

    with pytest.raises(CustomComponentValidationError, match="restricted to administrators"):
        await component.get_graph(flow_id_selected=binding.tool.flow_id)

    constructor.assert_not_called()
    loader.assert_awaited_once()


@pytest.mark.parametrize("is_superuser", [False, True])
async def test_frozen_dependency_build_uses_caller_policy(nested_env, monkeypatch, is_superuser):
    from lfx.base.tools import run_flow as run_flow_module

    nested_env.get_user_is_superuser.return_value = is_superuser
    component = _component()
    flow_id = str(uuid4())
    source = {"id": flow_id, "name": "Nested tool", **_child_flow_data("# frozen caller source").data}
    original = deepcopy(source)
    definitions = {flow_id: source}
    component._vertex = SimpleNamespace(graph=SimpleNamespace(frozen_tool_flows=definitions), data={})
    sanitized = {"nodes": [], "edges": []}
    prepare = AsyncMock(return_value=sanitized)
    graph = MagicMock(spec=Graph)
    constructor = Mock(return_value=graph)
    monkeypatch.setattr(run_flow_module, "prepare_flow_build_for_user", prepare)
    monkeypatch.setattr(run_flow_module.Graph, "from_payload", constructor)

    assert await component.get_graph(flow_id_selected=flow_id) is graph

    prepare.assert_awaited_once_with(original["data"], is_superuser=is_superuser)
    assert constructor.call_args.kwargs["payload"] is sanitized
    assert graph.frozen_tool_flows is definitions
    assert source == original


@pytest.mark.parametrize("warm_definition", [False, True])
async def test_frozen_dependency_denial_stops_graph_construction(nested_env, monkeypatch, warm_definition):  # noqa: ARG001
    from lfx.base.tools import run_flow as run_flow_module

    component = _component()
    flow_id = str(uuid4())
    source = {"id": flow_id, "name": "Nested tool", **_child_flow_data("# frozen caller source").data}
    component._vertex = SimpleNamespace(graph=SimpleNamespace(frozen_tool_flows={flow_id: source}), data={})
    prepare = AsyncMock(return_value=None)
    constructor = Mock(return_value=MagicMock(spec=Graph))
    monkeypatch.setattr(run_flow_module, "prepare_flow_build_for_user", prepare)
    monkeypatch.setattr(run_flow_module.Graph, "from_payload", constructor)
    if warm_definition:
        await component.get_graph(flow_id_selected=flow_id)
        constructor.reset_mock()
    prepare.side_effect = CustomComponentValidationError("custom components are restricted to administrators")

    with pytest.raises(CustomComponentValidationError, match="restricted to administrators"):
        await component.get_graph(flow_id_selected=flow_id)

    constructor.assert_not_called()


@pytest.fixture
def reviewed_snapshot_env(monkeypatch):
    from lfx.projects import invocation
    from lfx.projects.bindings import FlowBinding

    component = _component()
    parent = Graph()
    parent.set_run_id()
    component._vertex = SimpleNamespace(graph=parent, data={})
    binding = FlowBinding(flow_id=str(uuid4()), node_id="prompt", output_name="message", revision="a" * 64)
    monkeypatch.setattr(component, "_instruction_binding", lambda: binding)
    source = {"name": "Reviewed instructions", **_child_flow_data("# reviewed caller source").data}
    loader = AsyncMock(return_value=source)
    monkeypatch.setattr(invocation, "reviewed_flow_source", loader)
    return SimpleNamespace(component=component, binding=binding, source=source, loader=loader)


@pytest.mark.parametrize("is_superuser", [False, True])
async def test_reviewed_snapshot_rechecks_caller_policy(nested_env, reviewed_snapshot_env, monkeypatch, is_superuser):
    from lfx.base.tools import run_flow as run_flow_module

    env = reviewed_snapshot_env
    nested_env.get_user_is_superuser.return_value = is_superuser
    original = deepcopy(env.source)
    sanitized = {"nodes": [], "edges": []}
    prepare = AsyncMock(return_value=sanitized)
    constructor = Mock(side_effect=[MagicMock(spec=Graph), MagicMock(spec=Graph)])
    monkeypatch.setattr(run_flow_module, "prepare_flow_build_for_user", prepare)
    monkeypatch.setattr(run_flow_module.Graph, "from_payload", constructor)

    first = await env.component.get_graph(flow_id_selected=env.binding.flow_id)
    second = await env.component.get_graph(flow_id_selected=env.binding.flow_id)

    assert first is not second
    env.loader.assert_awaited_once()
    assert prepare.await_count == 2
    for call in prepare.await_args_list:
        assert call.args[0] == original["data"]
        assert call.kwargs["is_superuser"] is is_superuser
    assert all(call.kwargs["payload"] is sanitized for call in constructor.call_args_list)
    assert env.source == original


@pytest.mark.parametrize("warm_definition", [False, True])
@pytest.mark.usefixtures("nested_env")
async def test_reviewed_snapshot_denial_stops_graph_construction(
    reviewed_snapshot_env,
    monkeypatch,
    warm_definition,
):
    from lfx.base.tools import run_flow as run_flow_module

    env = reviewed_snapshot_env
    prepare = AsyncMock(return_value=None)
    constructor = Mock(return_value=MagicMock(spec=Graph))
    monkeypatch.setattr(run_flow_module, "prepare_flow_build_for_user", prepare)
    monkeypatch.setattr(run_flow_module.Graph, "from_payload", constructor)
    if warm_definition:
        await env.component.get_graph(flow_id_selected=env.binding.flow_id)
        constructor.reset_mock()
    prepare.side_effect = CustomComponentValidationError("custom components are restricted to administrators")

    with pytest.raises(CustomComponentValidationError, match="restricted to administrators"):
        await env.component.get_graph(flow_id_selected=env.binding.flow_id)

    constructor.assert_not_called()
    env.loader.assert_awaited_once()
