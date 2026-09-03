from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
from lfx.cli.validation import validate_connection_refs_for_env
from lfx.custom.custom_component.component import Component
from lfx.graph.graph.base import Graph
from lfx.inputs.inputs import ConnectionRefInput
from lfx.integrations import ConnectionUnresolvedError, ResolvedCredential, integration_action
from lfx.run._defaults import apply_run_defaults
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.schema import ServiceType
from pydantic import SecretStr


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


def test_headless_preflight_reports_missing_connection(monkeypatch: pytest.MonkeyPatch) -> None:
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
    graph = SimpleNamespace(vertices=[vertex], context={})

    errors = validate_connection_refs_for_env(graph)

    assert len(errors) == 1
    assert isinstance(errors[0], ConnectionUnresolvedError)
    assert errors[0].env_key == "LF_CONNECTION__TEST_2EPROVIDER__WORK"


@pytest.mark.asyncio
async def test_integration_telemetry_excludes_connection_identifiers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = []

    class Telemetry:
        async def send_telemetry_data(self, payload, event_name):
            captured.append((payload, event_name))

    manager = SimpleNamespace(services={ServiceType.TELEMETRY_SERVICE: Telemetry()})
    monkeypatch.setattr("lfx.services.manager.get_service_manager", lambda: manager)
    component = SimpleNamespace(
        graph=SimpleNamespace(execution_principal=ExecutionPrincipal(kind="headless_operator")),
        log=lambda *_args, **_kwargs: None,
    )

    async with integration_action(component, provider="google", capability="drive.read", owner_kind="env"):
        pass

    payload, event_name = captured[0]
    rendered = payload.model_dump()
    assert event_name == "integration_action"
    assert set(rendered) == {
        "client_type",
        "provider",
        "capability",
        "ms",
        "success",
        "error_code",
        "owner_kind",
        "principal_kind",
    }
    assert "connection" not in rendered
