"""Unsupported integrations fail before headless credential setup or execution."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from lfx.cli.validation import validate_connection_refs_for_env
from lfx.custom.custom_component.component import Component
from lfx.integrations.errors import IntegrationContextUnsupportedError
from lfx.io import ConnectionRefInput, Output
from lfx.services.authorization.base import ExecutionPrincipal


class JiraProbe(Component):
    inputs = [ConnectionRefInput(name="connection", provider="jira", capabilities=["jira.issue.read"])]
    outputs = [Output(name="result", display_name="Result", method="read_issue")]

    def read_issue(self):
        pytest.fail("Unsupported action must not run")


@pytest.fixture
def registry(monkeypatch):
    capability = SimpleNamespace(
        id="jira.issue.read",
        component_ref="JiraProbe",
        policy_keys=("integrations.jira.issue.read",),
        deployment_contexts=("hosted", "self_managed"),
    )
    manifest = SimpleNamespace(display_name="Jira Cloud", capabilities=[capability])
    monkeypatch.setattr(
        "lfx.extension.bundle_registry.get_default_registry",
        lambda: SimpleNamespace(
            list_integrations=lambda: [SimpleNamespace(provider_id="jira", capability_manifest=manifest)]
        ),
    )
    return capability


def component(*, headless=True):
    node = JiraProbe(connection="jira/work")
    node.set_vertex(
        SimpleNamespace(
            outgoing_edges=[],
            graph=SimpleNamespace(
                execution_principal=ExecutionPrincipal(kind="headless_operator" if headless else "actor"),
                flow_id="flow",
                session_id="session",
            ),
        )
    )
    return node


@pytest.mark.usefixtures("registry")
def test_unsupported_context_precedes_resolver(monkeypatch):
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: pytest.fail("Resolved credentials"))
    with pytest.raises(IntegrationContextUnsupportedError, match=r"Jira Cloud.*not available in headless lfx"):
        component().resolve_connection("connection")


@pytest.mark.usefixtures("registry")
async def test_unsupported_context_precedes_component_body(monkeypatch):
    node = component()
    send_message = AsyncMock()
    monkeypatch.setattr(node, "send_message", send_message)
    with pytest.raises(IntegrationContextUnsupportedError):
        await node.build_results()
    assert "action-unsupported" in send_message.call_args.args[0].model_dump_json()


@pytest.mark.parametrize("injected", [False, True])
@pytest.mark.usefixtures("registry")
def test_cli_context_error_precedes_environment_setup(monkeypatch, *, injected):
    if injected:
        monkeypatch.setenv("LF_CONNECTION__JIRA__WORK", "synthetic-token")
    else:
        monkeypatch.delenv("LF_CONNECTION__JIRA__WORK", raising=False)
    graph = SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="headless_operator"),
        context={},
        vertices=[
            SimpleNamespace(
                params={},
                data={
                    "node": {
                        "template": {
                            "connection": {
                                "type": "connection_ref",
                                "provider": "jira",
                                "capabilities": ["jira.issue.read"],
                                "value": "jira/work",
                            }
                        }
                    }
                },
            )
        ],
    )
    errors = validate_connection_refs_for_env(graph)
    assert len(errors) == 1
    assert isinstance(errors[0], IntegrationContextUnsupportedError)
    assert "LF_CONNECTION" not in str(errors[0])


@pytest.mark.parametrize("supported", [False, True])
def test_hosted_execution_and_supported_headless_remain_available(monkeypatch, registry, *, supported):
    if supported:
        registry.deployment_contexts = ("headless",)
    resolver = SimpleNamespace()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    lease = component(headless=supported).resolve_connection("connection")
    assert lease is not None
