"""Unit tests for CapabilityService."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from lfx.services.capability import (
    AllTrustedClassifier,
    CapabilityClaims,
    CapabilityContext,
    CapabilityService,
    NoopCapabilityProvider,
    SingleTenantResolver,
    Trust,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class _StubSettings:
    settings = type("Settings", (), {})()


@pytest.fixture
def service() -> CapabilityService:
    return CapabilityService(settings_service=_StubSettings())


def test_defaults_are_passthrough(service: CapabilityService) -> None:
    assert service.is_passthrough is True
    assert isinstance(service.provider, NoopCapabilityProvider)
    assert isinstance(service.classifier, AllTrustedClassifier)
    assert isinstance(service.resolver, SingleTenantResolver)


def test_passthrough_route_keeps_default_executor_without_runtime_metadata(service: CapabilityService) -> None:
    decision = service.route(graph=None, user_id="u1", flow_id="f1", run_id="r1")

    assert decision.executor_kind == "in-process"
    assert decision.capability_token is None
    assert decision.runtime_options == {}
    assert decision.trust is Trust.TRUSTED


def test_install_swaps_primitives(service: CapabilityService) -> None:
    class _Classifier:
        def trust_of_flow(self, context: CapabilityContext) -> Trust:  # noqa: ARG002
            return Trust.UNTRUSTED

        def is_untrusted_node(self, _node: dict[str, Any], _context: CapabilityContext | None = None) -> bool:
            return True

    class _Resolver:
        def resolve(self, context: CapabilityContext) -> str:
            assert context.user_id == "u1"
            return "tenant-u1"

    class _Provider:
        def mint(
            self,
            *,
            context: CapabilityContext,
            tenant_id: str,
            component_id: str | None,
            scopes: Sequence[str],
            ttl_seconds: int = 600,  # noqa: ARG002
        ) -> str:
            assert context.flow_id == "f1"
            assert tenant_id == "tenant-u1"
            assert component_id is None
            assert tuple(scopes) == ("variables:read",)
            return "cap-token"

        def verify(self, token: str) -> CapabilityClaims:  # noqa: ARG002
            return CapabilityClaims(tenant_id="tenant-u1", user_id="u1")

    service.install(
        provider=_Provider(),
        classifier=_Classifier(),
        resolver=_Resolver(),
        untrusted_executor_kind="sandbox",
    )

    decision = service.route(
        graph=None,
        user_id="u1",
        flow_id="f1",
        run_id="r1",
        default_executor_kind="in-process",
        scopes=("variables:read",),
    )

    assert service.is_passthrough is False
    assert decision.executor_kind == "sandbox"
    assert decision.capability_token == "cap-token"  # noqa: S105
    assert decision.runtime_options == {
        "lfx_capability_token": "cap-token",
        "lfx_tenant_id": "tenant-u1",
        "lfx_trust": "untrusted",
    }
