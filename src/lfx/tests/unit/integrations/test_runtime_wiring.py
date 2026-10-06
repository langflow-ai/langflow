from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from lfx.cli.validation import validate_connection_refs_for_env
from lfx.custom.custom_component.component import Component
from lfx.graph.graph.base import Graph
from lfx.inputs.inputs import ConnectionRefInput
from lfx.integrations import (
    ConditionalScopeRequirement,
    ConnectionUnresolvedError,
    ResolvedCredential,
    ScopeCondition,
    integration_action,
)
from lfx.io import BoolInput
from lfx.run._defaults import apply_run_defaults
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.schema import ServiceType
from pydantic import SecretStr

if TYPE_CHECKING:
    from pathlib import Path


class ConnectionComponent(Component):
    inputs = [
        ConnectionRefInput(
            name="connection",
            provider="google",
            required_scopes=["drive.read"],
        )
    ]


class CapturingResolver:
    def __init__(self) -> None:
        self.request = None

    async def resolve(self, request):
        self.request = request
        return ResolvedCredential(access_token=SecretStr("runtime-token"), provider="google", name="work")

    async def describe(self, _ref, _principal):
        return None


def test_headless_principal_is_in_memory_and_propagated_to_graph_copies() -> None:
    graph = Graph()
    apply_run_defaults(graph, session_id="session-1", user_id="operator-1")

    graph_copy = copy.deepcopy(graph)

    assert graph.execution_principal.kind == "headless_operator"
    assert graph_copy.execution_principal == graph.execution_principal
    assert "execution_principal" not in graph.__getstate__()


@pytest.mark.asyncio
async def test_component_builds_lazy_lease_from_graph_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = CapturingResolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    component = ConnectionComponent(connection="google/work")
    graph = SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True),
        flow_id="flow-1",
        run_id="run-1",
    )
    component.set_vertex(SimpleNamespace(graph=graph))

    lease = component.resolve_connection("connection")

    assert resolver.request is None
    assert await lease.get_token() == "runtime-token"
    assert resolver.request.principal.user_id == "user-1"
    assert resolver.request.required_scopes == frozenset({"drive.read"})


@pytest.mark.parametrize("no_env_fallback", [False, True])
def test_headless_preflight_reports_missing_connection(monkeypatch: pytest.MonkeyPatch, no_env_fallback) -> None:
    monkeypatch.delenv("LF_CONNECTION__TEST_2EPROVIDER__WORK", raising=False)
    vertex = SimpleNamespace(
        data={
            "node": {
                "template": {
                    "connection": {"type": "connection_ref", "value": "test.provider/work"},
                }
            }
        },
        params={"connection": "test.provider/work"},
    )
    graph = SimpleNamespace(vertices=[vertex], context={"no_env_fallback": no_env_fallback})

    errors = validate_connection_refs_for_env(graph)

    assert len(errors) == 1
    assert isinstance(errors[0], ConnectionUnresolvedError)
    assert errors[0].env_key == "LF_CONNECTION__TEST_2EPROVIDER__WORK"
    assert errors[0].reason == ("env-fallback-disabled" if no_env_fallback else "missing")
    if no_env_fallback:
        assert "Set LF_CONNECTION" not in str(errors[0])


@pytest.mark.asyncio
async def test_integration_action_logs_without_product_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    logs = []

    manager = SimpleNamespace(services={ServiceType.TELEMETRY_SERVICE: SimpleNamespace()})
    monkeypatch.setattr("lfx.services.manager.get_service_manager", lambda: manager)
    component = SimpleNamespace(
        graph=SimpleNamespace(execution_principal=ExecutionPrincipal(kind="headless_operator")),
        log=lambda *args, **kwargs: logs.append((args, kwargs)),
    )

    async with integration_action(component, provider="google", capability="drive.read", owner_kind="env"):
        pass

    assert logs
    assert logs[0][0][0]["provider"] == "google"
    assert logs[0][0][0]["capability"] == "drive.read"
    assert logs[0][0][0]["success"] is True


@pytest.mark.parametrize("write", [False, True])
async def test_real_graph_lease_before_run_enforces_active_conditional_scopes(
    monkeypatch: pytest.MonkeyPatch,
    write: bool,  # noqa: FBT001 - parametrized conditional input
) -> None:
    class ConditionalComponent(Component):
        inputs = [
            BoolInput(name="write", value=False),
            ConnectionRefInput(
                name="connection",
                provider="google",
                required_scopes=["drive.read"],
                conditional_scopes=[
                    ConditionalScopeRequirement(
                        scope="drive.write",
                        role="optional",
                        condition=ScopeCondition(kind="input_truthy", input="write"),
                    )
                ],
            ),
        ]

    resolver = CapturingResolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    graph = Graph()
    apply_run_defaults(graph, session_id="session", user_id="operator")
    component = ConditionalComponent(connection="google/work", write=write)
    component.set_vertex(SimpleNamespace(graph=graph))

    lease = component.resolve_connection("connection")
    assert resolver.request is None
    assert await lease.get_token() == "runtime-token"
    assert resolver.request.run_id is None
    assert resolver.request.required_scopes == frozenset({"drive.read", "drive.write"} if write else {"drive.read"})


async def test_subgraph_inherits_execution_principal() -> None:
    from lfx.components.input_output import TextOutputComponent
    from lfx.services.authorization.base import ExecutionPrincipal

    component = TextOutputComponent(_id="output").set(input_value="hello")
    graph = Graph(start=component, end=component)
    graph.execution_principal = ExecutionPrincipal(kind="actor", user_id="actor", family="v1_run", interactive=True)

    async with graph.create_subgraph({"output"}) as subgraph:
        assert subgraph.execution_principal == graph.execution_principal
        assert "execution_principal" not in subgraph.__getstate__()


def test_malformed_preflight_never_echoes_field_value() -> None:
    raw = "sensitive-token-value"
    graph = SimpleNamespace(
        vertices=[
            SimpleNamespace(
                data={"node": {"template": {"connection": {"type": "connection_ref", "value": raw}}}}, params={}
            )
        ],
        context={},
    )
    errors = validate_connection_refs_for_env(graph)
    assert len(errors) == 1
    assert errors[0].code == "connection-unresolved"
    assert raw not in str(errors[0])
    assert raw not in repr(vars(errors[0]))


async def test_integration_action_does_not_access_telemetry_service(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called():
        pytest.fail("product telemetry service must not be resolved")

    monkeypatch.setattr("lfx.services.manager.get_service_manager", fail_if_called)
    component = SimpleNamespace(graph=None, log=lambda *_args, **_kwargs: None)

    async with integration_action(component, provider="google", capability="drive.read", owner_kind="env"):
        pass


async def test_run_flow_uses_configured_resolver_without_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from lfx.run.base import run_flow
    from lfx.services.connection.base import BaseConnectionResolverService, ConnectionAccessPolicy
    from lfx.services.manager import get_service_manager

    class HostResolver(BaseConnectionResolverService):
        def __init__(self):
            super().__init__()
            self.set_ready()

        async def _get_access_policy(self, _request):
            return ConnectionAccessPolicy(owner_kind="env", allow_non_interactive=True)

        async def _resolve(self, request, _policy):
            return ResolvedCredential(access_token=SecretStr("host-only"), provider=request.ref.provider)

    manager = get_service_manager()
    monkeypatch.setitem(manager.service_classes, ServiceType.CONNECTION_RESOLVER_SERVICE, HostResolver)
    monkeypatch.delitem(manager.services, ServiceType.CONNECTION_RESOLVER_SERVICE, raising=False)
    monkeypatch.delenv("LF_CONNECTION__GOOGLE__WORK", raising=False)
    script = tmp_path / "connection_flow.py"
    script.write_text(
        """from lfx.custom import Component
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.io import ConnectionRefInput, MessageTextInput, Output
from lfx.schema.message import Message

class ConnectionProbe(Component):
    inputs = [MessageTextInput(name="input_value"), ConnectionRefInput(name="connection", provider="google")]
    outputs = [Output(name="result", method="resolve", display_name="Result")]

    async def resolve(self) -> Message:
        token = await self.resolve_connection("connection").get_token()
        return Message(text="resolved" if token == "host-only" else "incorrect credential")

chat = ChatInput(_id="chat").set(input_value="hello")
component = ConnectionProbe(_id="probe", connection="google/work").set(input_value=chat.message_response)
output = ChatOutput(_id="output").set(input_value=component.resolve)
graph = Graph(start=chat, end=output)
""",
        encoding="utf-8",
    )
    try:
        result = await run_flow(script_path=script, check_variables=True)
        assert result["success"] is True
        assert "resolved" in str(result)
        assert "host-only" not in str(result)
    finally:
        manager.services.pop(ServiceType.CONNECTION_RESOLVER_SERVICE, None)
