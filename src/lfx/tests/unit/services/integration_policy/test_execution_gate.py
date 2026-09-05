"""Execution enforcement of integration policy before any adapter runs (INT-7)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import ConnectionRefInput
from lfx.integrations import ResolvedCredential
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.integration_policy import IntegrationPolicyError, IntegrationPolicyService
from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot
from lfx.template.field.base import Output
from pydantic import SecretStr

SEARCH_CAPABILITY = "google.drive.files.search"
SEARCH_KEY = "integrations.google.drive.search"


class _Resolver:
    def __init__(self) -> None:
        self.request = None

    async def resolve(self, request):
        self.request = request
        return ResolvedCredential(access_token=SecretStr("token"), provider="google", name="work")

    async def describe(self, _ref, _principal):
        return None


class DriveComponent(Component):
    inputs = [
        ConnectionRefInput(
            name="connection",
            provider="google",
            required_scopes=["drive.file"],
            capabilities=[SEARCH_CAPABILITY],
        )
    ]
    outputs = [Output(name="result", display_name="Result", method="search")]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.adapter_calls = 0

    async def search(self):
        self.adapter_calls += 1
        return "searched"


def _install_policy(monkeypatch, bundle: PolicyBundleService) -> IntegrationPolicyService:
    from lfx.services import deps as lfx_deps

    service = IntegrationPolicyService(policy_bundle_service=bundle)
    monkeypatch.setattr(lfx_deps, "get_integration_policy_service", lambda: service)
    return service


def _install_capability_manifest(monkeypatch) -> None:
    """Expose one capability so its declared policy key is enforceable."""
    capability = SimpleNamespace(id=SEARCH_CAPABILITY, policy_keys=(SEARCH_KEY,), component_ref="DriveComponent")
    integration = SimpleNamespace(
        provider_id="google",
        capability_manifest=SimpleNamespace(provider_id="google", capabilities=(capability,)),
    )
    registry = SimpleNamespace(list_integrations=lambda: [integration])
    monkeypatch.setattr("lfx.extension.bundle_registry.get_default_registry", lambda: registry)


def _component(monkeypatch, resolver: _Resolver) -> DriveComponent:
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    component = DriveComponent(connection="google/work", _user_id="user-1")
    component.set_vertex(
        SimpleNamespace(
            graph=SimpleNamespace(
                execution_principal=ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True),
                flow_id="flow-1",
                run_id="run-1",
                session_id="session-1",
            )
        )
    )
    return component


def _blocked_bundle(*, providers: frozenset[str] = frozenset(), actions: frozenset[str] = frozenset()):
    bundle = PolicyBundleService()
    bundle.publish(
        PolicyBundleSnapshot(
            revision=1,
            initialized=True,
            approved_integration_provider_ids=providers,
            blocked_integration_action_keys=actions,
        )
    )
    return bundle


def test_resolve_connection_forwards_declared_capability_ids(monkeypatch) -> None:
    _install_policy(monkeypatch, PolicyBundleService())
    _install_capability_manifest(monkeypatch)
    resolver = _Resolver()
    lease = _component(monkeypatch, resolver).resolve_connection("connection")
    assert lease._request.capability_ids == frozenset({SEARCH_CAPABILITY})


def test_resolve_connection_refuses_a_lease_for_a_provider_outside_the_ceiling(monkeypatch) -> None:
    """QA: execution enforces provider policy before adapter invocation."""
    _install_policy(monkeypatch, _blocked_bundle(providers=frozenset({"slack"})))
    _install_capability_manifest(monkeypatch)
    resolver = _Resolver()
    component = _component(monkeypatch, resolver)

    with pytest.raises(IntegrationPolicyError):
        component.resolve_connection("connection")
    assert resolver.request is None


def test_resolve_connection_refuses_a_lease_for_a_blocked_action(monkeypatch) -> None:
    """QA: execution enforces action policy before adapter invocation."""
    _install_policy(monkeypatch, _blocked_bundle(actions=frozenset({SEARCH_KEY})))
    _install_capability_manifest(monkeypatch)
    resolver = _Resolver()
    component = _component(monkeypatch, resolver)

    with pytest.raises(IntegrationPolicyError) as excinfo:
        component.resolve_connection("connection")
    assert excinfo.value.policy_key == SEARCH_KEY
    assert resolver.request is None


async def test_build_results_fails_closed_before_the_component_body_runs(monkeypatch) -> None:
    """A blocked action must fail before the output method executes."""
    _install_policy(monkeypatch, _blocked_bundle(actions=frozenset({SEARCH_KEY})))
    _install_capability_manifest(monkeypatch)
    component = _component(monkeypatch, _Resolver())

    with pytest.raises(IntegrationPolicyError):
        await component.build_results()
    assert component.adapter_calls == 0


async def test_execution_gate_passes_through_when_no_integration_policy_is_set(monkeypatch) -> None:
    """QA: OSS pass-through behavior remains unchanged when no integration policy is set."""
    from lfx.services.integration_policy import IntegrationPolicyPurpose

    _install_policy(monkeypatch, PolicyBundleService())
    _install_capability_manifest(monkeypatch)
    resolver = _Resolver()
    component = _component(monkeypatch, resolver)

    # The same gate build_results() runs first, exercised without the vertex
    # plumbing a full build needs.
    component.require_integration_policy(IntegrationPolicyPurpose.USE)
    lease = component.resolve_connection("connection")

    assert await lease.get_token() == "token"
    assert resolver.request is not None


def test_require_integration_policy_is_a_no_op_without_connection_inputs(monkeypatch) -> None:
    from lfx.services.integration_policy import IntegrationPolicyPurpose

    _install_policy(monkeypatch, _blocked_bundle(providers=frozenset({"slack"})))

    class Plain(Component):
        inputs = []
        outputs = []

    Plain().require_integration_policy(IntegrationPolicyPurpose.USE)
