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
        explicit_share_authorized: bool = False,
    ) -> IntegrationError | None:
        """Apply the portable deny floor, including a host-verified share decision.

        Only a host may set ``explicit_share_authorized``, after checking the
        actor's connection:execute grant and the route family's share policy.
        It must never come from flow JSON or component input. A share can satisfy
        an actor's owner mismatch; it cannot override any other deny below.
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
            if connection_owner_id is None or principal.user_id is None:
                return ConnectionNotAuthorizedError(provider=request.ref.provider)
            if not principal.interactive and not allow_non_interactive:
                return ConnectionNotAuthorizedError(provider=request.ref.provider)
            if str(principal.user_id) != str(connection_owner_id) and not (
                principal.kind == "actor" and explicit_share_authorized
            ):
                return ConnectionNotAuthorizedError(provider=request.ref.provider)
        return None

    async def teardown(self) -> None:
        """Resolvers own no resources by default."""
