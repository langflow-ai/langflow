"""Exercise action selection through graph builds, agent tools and credential leases."""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar

import pytest
from langchain_core.tools import StructuredTool, ToolException
from lfx.base.tools.component_tool import ComponentToolkit
from lfx.custom import Component
from lfx.graph import Graph
from lfx.graph.graph.schema import VertexBuildResult
from lfx.integrations.errors import ActionUnsupportedError
from lfx.io import ConnectionRefInput, DropdownInput, HandleInput, Output
from lfx.services.integration_policy import IntegrationPolicyError, IntegrationPolicyService
from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot

SEARCH = "qaprobe.doc.search"
DELETE = "qaprobe.doc.delete"
DELETE_KEY = "integrations.qaprobe.doc.delete"


class ActionPicker(Component):
    inputs = [DropdownInput(name="action", options=["search", "delete"], value="search", tool_mode=True)]
    outputs = [Output(name="result", display_name="Result", method="execute")]
    calls: ClassVar[list[str]] = []

    def select_integration_capabilities(self, capability_ids: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(capability for capability in capability_ids if capability == f"qaprobe.doc.{self.action}")

    def execute(self) -> str:
        self.calls.append(self.action)
        return f"ran {self.action}"


class AsyncActionPicker(ActionPicker):
    async def execute(self) -> str:
        return super().execute()


class ConnectionActionPicker(AsyncActionPicker):
    inputs = [
        *ActionPicker.inputs,
        ConnectionRefInput(name="connection", provider="qaprobe", capabilities=[SEARCH, DELETE]),
    ]


class FixedAction(Component):
    inputs = []
    outputs = [Output(name="result", display_name="Result", method="execute")]
    calls: ClassVar[list[str]] = []

    def execute(self) -> str:
        self.calls.append("delete")
        return "adapter ran"


class AsyncFixedAction(FixedAction):
    async def execute(self) -> str:
        return super().execute()


class ToolCaller(Component):
    inputs = [
        HandleInput(name="tools", input_types=["Tool"], is_list=True),
        DropdownInput(name="action", options=["search", "delete"], value="search"),
    ]
    outputs = [Output(name="result", display_name="Result", method="execute")]

    async def execute(self) -> str:
        return await self.tools[0].coroutine(action=self.action)


async def _invoke(tool, **kwargs):
    if tool.coroutine:
        return await tool.coroutine(**kwargs)
    return tool.func(**kwargs)


@pytest.fixture
def install_policy(monkeypatch):
    def install(component_class, *, providers=frozenset(), actions=frozenset({DELETE_KEY})):
        bundle = PolicyBundleService()
        bundle.publish(
            PolicyBundleSnapshot(
                revision=1,
                initialized=True,
                approved_integration_provider_ids=providers,
                blocked_integration_action_keys=actions,
            )
        )
        service = IntegrationPolicyService(policy_bundle_service=bundle)
        monkeypatch.setattr("lfx.services.deps.get_integration_policy_service", lambda: service)
        ids = (SEARCH, DELETE) if issubclass(component_class, ActionPicker) else (DELETE,)
        integration = SimpleNamespace(
            provider_id="qaprobe",
            capability_manifest=SimpleNamespace(
                capabilities=tuple(
                    SimpleNamespace(
                        id=capability_id,
                        policy_keys=(f"integrations.{capability_id}",),
                        component_ref=component_class.__name__,
                    )
                    for capability_id in ids
                )
            ),
        )
        monkeypatch.setattr(
            "lfx.extension.bundle_registry.get_default_registry",
            lambda: SimpleNamespace(list_integrations=lambda: [integration]),
        )
        component_class.calls.clear()
        return bundle, service

    return install


@pytest.mark.parametrize("component_class", [FixedAction, AsyncFixedAction])
@pytest.mark.parametrize("block_provider", [False, True])
async def test_api_key_tool_gate_precedes_adapter(install_policy, component_class, *, block_provider):
    install_policy(component_class, providers=frozenset({"other"}) if block_provider else frozenset())
    tool = ComponentToolkit(component=component_class()).get_tools()[0]

    with pytest.raises(ToolException) as caught:
        await _invoke(tool)

    assert isinstance(caught.value.__cause__, IntegrationPolicyError)
    assert component_class.calls == []


@pytest.mark.parametrize("component_class", [ActionPicker, AsyncActionPicker, ConnectionActionPicker])
@pytest.mark.parametrize("action", ["search", "delete"])
async def test_build_enforces_only_the_selected_action(install_policy, component_class, action):
    install_policy(component_class)
    component = component_class(action=action)

    if action == "delete":
        with pytest.raises(IntegrationPolicyError):
            await component.build_results()
        assert component_class.calls == []
    else:
        results, _ = await component.build_results()
        assert results["result"] == "ran search"
        assert component_class.calls == ["search"]


@pytest.mark.parametrize("component_class", [ActionPicker, AsyncActionPicker, ConnectionActionPicker])
async def test_tool_selection_uses_each_calls_arguments(install_policy, component_class):
    install_policy(component_class)
    tool = ComponentToolkit(component=component_class(action="delete")).get_tools()[0]

    # The saved action is blocked, but this invocation explicitly selects search.
    assert await _invoke(tool, action="search") == "ran search"
    with pytest.raises(ToolException):
        await _invoke(tool, action="delete")
    assert component_class.calls == ["search"]


def test_lease_forwards_only_the_selected_capability(install_policy):
    install_policy(ConnectionActionPicker)
    component = ConnectionActionPicker(action="search", connection="qaprobe/work")

    lease = component.resolve_connection("connection")

    assert lease._request.capability_ids == frozenset({SEARCH})
    component.set(action="delete")
    with pytest.raises(IntegrationPolicyError):
        component.resolve_connection("connection")


@pytest.mark.parametrize("selection", [(), ("qaprobe.doc.unknown",), (SEARCH, "other.action")])
def test_invalid_selection_cannot_remove_the_gate(install_policy, monkeypatch, selection):
    install_policy(ActionPicker)
    component = ActionPicker()
    monkeypatch.setattr(component, "select_integration_capabilities", lambda _: selection)

    with pytest.raises(ActionUnsupportedError) as caught:
        component.require_integration_policy()
    assert caught.value.http_status == 422
    assert caught.value.code == "action-unsupported"
    assert ActionPicker.calls == []


async def test_tool_rechecks_policy_after_creation(install_policy):
    bundle, service = install_policy(AsyncFixedAction, actions=frozenset())
    tool = ComponentToolkit(component=AsyncFixedAction()).get_tools()[0]
    assert await tool.coroutine() == "adapter ran"
    bundle.publish(PolicyBundleSnapshot(revision=2, initialized=True, blocked_integration_action_keys={DELETE_KEY}))
    service.invalidate()  # The policy writer invalidates dependent services after publication.

    with pytest.raises(ToolException):
        await tool.coroutine()
    assert AsyncFixedAction.calls == ["delete"]


@pytest.mark.parametrize("action", ["search", "delete"])
@pytest.mark.parametrize("block_provider", [False, True])
async def test_graph_can_construct_a_tool_before_its_action_is_selected(install_policy, action, *, block_provider):
    from lfx.exceptions.component import ComponentBuildError

    install_policy(AsyncActionPicker, providers=frozenset({"other"}) if block_provider else frozenset())
    picker = AsyncActionPicker(_id="picker", action="delete")
    picker._append_tool_to_outputs_map()
    caller = ToolCaller(_id="caller", action=action).set(tools=picker.to_toolkit)
    graph = Graph(start=picker, end=caller)

    async def run():
        return [result async for result in graph.async_start()]

    if block_provider or action == "delete":
        with pytest.raises(ComponentBuildError):
            await run()
        assert AsyncActionPicker.calls == []
    else:
        results = await run()
        builds = [result for result in results if isinstance(result, VertexBuildResult)]
        assert len(builds) == 2
        assert all(result.valid for result in builds)
        assert AsyncActionPicker.calls == ["search"]


class CustomToolset(ActionPicker):
    constructions: ClassVar[list[str]] = []

    async def _get_tools(self):
        self.constructions.append("constructed")

        async def delete() -> str:
            """Delete a document."""
            self.calls.append("delete")
            return "deleted"

        return [StructuredTool.from_function(coroutine=delete)]


class ConnectionToolset(CustomToolset):
    inputs = ConnectionActionPicker.inputs
    leases: ClassVar[list] = []

    async def _get_tools(self):
        self.leases.append(self.resolve_connection("connection"))
        return await super()._get_tools()


class CustomToolCaller(ToolCaller):
    async def execute(self) -> str:
        return await self.tools[0].ainvoke({})


@pytest.mark.parametrize("component_class", [CustomToolset, ConnectionToolset])
@pytest.mark.parametrize("via_graph", [False, True])
@pytest.mark.parametrize("blocked", [{DELETE_KEY}, {DELETE_KEY, f"integrations.{SEARCH}"}])
async def test_custom_toolsets_require_every_action_before_construction(
    install_policy, component_class, via_graph, blocked
):
    install_policy(component_class, actions=frozenset(blocked))
    CustomToolset.constructions.clear()
    ConnectionToolset.leases.clear()
    component = component_class(action="search")
    if component_class is ConnectionToolset:
        component.set(connection="qaprobe/work")
    component._append_tool_to_outputs_map()
    caller = CustomToolCaller().set(tools=component.to_toolkit)
    graph = Graph(start=component, end=caller)

    if via_graph:
        from lfx.exceptions.component import ComponentBuildError

        with pytest.raises(ComponentBuildError):
            async for _ in graph.async_start():
                pass
    else:
        with pytest.raises(IntegrationPolicyError):
            await component.to_toolkit()
    assert CustomToolset.constructions == []
    assert ConnectionToolset.leases == []
    assert component_class.calls == []


async def test_custom_toolset_lease_covers_all_returned_actions_when_unrestricted(install_policy):
    install_policy(ConnectionToolset, actions=frozenset())
    ConnectionToolset.leases.clear()
    component = ConnectionToolset(action="search", connection="qaprobe/work")
    tools = await component.to_toolkit()
    assert ConnectionToolset.leases[-1]._request.capability_ids == frozenset({SEARCH, DELETE})
    assert await tools[0].ainvoke({}) == "deleted"


async def test_invalid_selection_is_not_a_policy_denial_without_policy(install_policy):
    install_policy(ActionPicker, actions=frozenset())
    with pytest.raises(ActionUnsupportedError) as caught:
        await ActionPicker(action="purge").build_results()
    assert caught.value.http_status == 422
    assert caught.value.code == "action-unsupported"
    assert ActionPicker.calls == []
