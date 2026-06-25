"""Protocols and value objects for pluggable execution capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


RESERVED_CAPABILITY_RUNTIME_OPTION_KEYS: frozenset[str] = frozenset(
    {
        "lfx_capability_token",
        "lfx_tenant_id",
        "lfx_trust",
    }
)


class Trust(str, Enum):
    """Trust classification used by execution policy plugins."""

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


@dataclass(frozen=True)
class CapabilityContext:
    """Context passed to capability plugins for one graph run."""

    graph: Any
    user_id: str | None = None
    flow_id: str | None = None
    run_id: str | None = None
    runtime_options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityClaims:
    """Claims returned by a capability provider after token verification."""

    tenant_id: str
    user_id: str
    flow_id: str | None = None
    run_id: str | None = None
    component_id: str | None = None
    scopes: tuple[str, ...] = ()


class CapabilityProvider(Protocol):
    """Mints and verifies opaque capability tokens.

    Core Langflow does not interpret token contents. Enterprise or other
    extensions can install a provider that mints tokens for a remote executor,
    worker gateway, or runtime API.
    """

    def mint(
        self,
        *,
        context: CapabilityContext,
        tenant_id: str,
        component_id: str | None,
        scopes: Sequence[str],
        ttl_seconds: int = 600,
    ) -> str | None: ...

    def verify(self, token: str) -> CapabilityClaims: ...


class TrustClassifier(Protocol):
    """Decides whether a run can use the default executor or needs another one."""

    def trust_of_flow(self, context: CapabilityContext) -> Trust: ...

    def is_untrusted_node(self, node: dict[str, Any], context: CapabilityContext | None = None) -> bool: ...


class TenantResolver(Protocol):
    """Maps run context to the tenant id used by capability providers."""

    def resolve(self, context: CapabilityContext) -> str: ...


@dataclass(frozen=True)
class RoutingDecision:
    """The capability service's routing answer for one graph run."""

    executor_kind: str
    tenant_id: str
    trust: Trust
    capability_token: str | None = None
    scopes: tuple[str, ...] = ()
    runtime_options: dict[str, Any] = field(default_factory=dict)
