"""Host-pluggable connection resolver contract."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Literal

from lfx.integrations.errors import ConnectionNotAuthorizedError, IntegrationError
from lfx.services.base import Service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.integrations.models import (
        ConnectionRef,
        ConnectionResolutionRequest,
        ConnectionStatus,
        ResolvedCredential,
    )
    from lfx.services.authorization.base import ExecutionPrincipal


class BaseConnectionResolverService(Service, abc.ABC):
    """Resolve portable connection handles inside the current host boundary."""

    name = ServiceType.CONNECTION_RESOLVER_SERVICE.value

    @abc.abstractmethod
    async def resolve(self, request: ConnectionResolutionRequest) -> ResolvedCredential:
        """Resolve a reference to a short-lived credential."""

    async def describe(
        self,
        ref: ConnectionRef,
        principal: ExecutionPrincipal,
    ) -> ConnectionStatus | None:
        """Return credential-free status when the host supports discovery."""
        _ = (ref, principal)
        return None

    def authorize_principal(
        self,
        request: ConnectionResolutionRequest,
        *,
        connection_owner_id: str | None,
        owner_kind: Literal["user", "instance", "env"],
        allow_non_interactive: bool,
    ) -> IntegrationError | None:
        """Apply the portable deny floor before a host adds share/policy checks.

        The floor never admits an explicit share: an owner mismatch on a user-owned
        row is a denial here, and only a host that can evaluate share grants may
        widen it. A host that does so must first honor
        ``request.principal.allow_explicit_shares`` — owner-only route families
        (the legacy MCP transports) set it to ``False`` and must not resolve a
        shared row. Instance-owned rows keep the floor's
        rule: any principal except ``anonymous_public``/``unknown`` may resolve
        them, and a host policy hook may narrow that further.
        """
        principal = request.principal
        if owner_kind == "env":
            return (
                None
                if principal.kind == "headless_operator"
                else ConnectionNotAuthorizedError(provider=request.ref.provider)
            )
        if principal.kind in {"anonymous_public", "unknown"}:
            return ConnectionNotAuthorizedError(provider=request.ref.provider)
        if owner_kind == "user":
            if connection_owner_id is None:
                return ConnectionNotAuthorizedError(provider=request.ref.provider)
            if not principal.interactive and not allow_non_interactive:
                return ConnectionNotAuthorizedError(provider=request.ref.provider)
            if str(principal.user_id) != str(connection_owner_id):
                return ConnectionNotAuthorizedError(provider=request.ref.provider)
        return None

    async def teardown(self) -> None:
        """Resolvers own no resources by default."""
