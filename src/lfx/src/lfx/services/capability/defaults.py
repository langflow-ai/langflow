"""Pass-through defaults for the capability service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.capability.protocols import CapabilityClaims, CapabilityContext, Trust

if TYPE_CHECKING:
    from collections.abc import Sequence


class NoopCapabilityProvider:
    """No-op provider used when no capability plugin is installed."""

    WILDCARD_SCOPE = "*"

    def mint(
        self,
        *,
        context: CapabilityContext,  # noqa: ARG002
        tenant_id: str,  # noqa: ARG002
        component_id: str | None,  # noqa: ARG002
        scopes: Sequence[str],  # noqa: ARG002
        ttl_seconds: int = 600,  # noqa: ARG002
    ) -> str | None:
        return None

    def verify(self, token: str) -> CapabilityClaims:  # noqa: ARG002
        return CapabilityClaims(
            tenant_id=SingleTenantResolver.DEFAULT_TENANT,
            user_id=SingleTenantResolver.DEFAULT_TENANT,
            scopes=(self.WILDCARD_SCOPE,),
        )


class AllTrustedClassifier:
    """Classifier that keeps every run on the default executor."""

    def trust_of_flow(self, context: CapabilityContext) -> Trust:  # noqa: ARG002
        return Trust.TRUSTED

    def is_untrusted_node(
        self, _node: dict[str, object], _context: CapabilityContext | None = None
    ) -> bool:
        return False


class SingleTenantResolver:
    """Resolver used by the pass-through default."""

    DEFAULT_TENANT = "default"

    def resolve(self, context: CapabilityContext) -> str:  # noqa: ARG002
        return self.DEFAULT_TENANT
