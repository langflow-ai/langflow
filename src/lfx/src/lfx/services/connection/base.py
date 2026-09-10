"""Host-pluggable connection resolver contract."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Literal, final

from pydantic import BaseModel, ConfigDict, StrictStr

from lfx.integrations.capabilities import ScopeSet
from lfx.integrations.errors import ConnectionNotAuthorizedError, IntegrationError, ScopeMissingError
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


class ConnectionAccessPolicy(BaseModel):
    """Host-owned metadata, loaded without decrypting or refreshing credentials.

    This policy must describe the same connection passed to ``_resolve``. Share
    decisions come from host authorization, never flow JSON or component input.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    owner_kind: Literal["user", "instance", "env"]
    connection_owner_id: StrictStr | None = None
    connection_id: StrictStr | None = None
    allow_non_interactive: bool = False
    explicit_share_authorized: bool = False


class BaseConnectionResolverService(Service, abc.ABC):
    """Resolve portable connection handles inside the current host boundary."""

    name = ServiceType.CONNECTION_RESOLVER_SERVICE.value

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if cls.resolve is not BaseConnectionResolverService.resolve:
            msg = "Connection resolvers must implement _get_access_policy and _resolve; resolve cannot be overridden"
            raise TypeError(msg)

    @final
    async def resolve(self, request: ConnectionResolutionRequest) -> ResolvedCredential:
        """Enforce the portable floor before invoking the host's credential hook."""
        if request.principal.kind in {"anonymous_public", "unknown"}:
            raise ConnectionNotAuthorizedError(provider=request.ref.provider)
        policy = await self._get_access_policy(request)
        if not isinstance(policy, ConnectionAccessPolicy):
            raise ConnectionNotAuthorizedError(provider=request.ref.provider)
        denial = BaseConnectionResolverService.authorize_principal(
            self,
            request,
            connection_owner_id=policy.connection_owner_id,
            owner_kind=policy.owner_kind,
            allow_non_interactive=policy.allow_non_interactive,
            explicit_share_authorized=policy.explicit_share_authorized,
        )
        if denial is not None:
            raise denial
        credential = await self._resolve(request, policy)
        if request.required_scopes and not credential.scopes_verified:
            raise ScopeMissingError(request.required_scopes, provider=request.ref.provider, scopes_verified=False)
        missing = ScopeSet.missing(
            provider=request.ref.provider, required=request.required_scopes, granted=credential.granted_scopes
        )
        if missing:
            raise ScopeMissingError(frozenset(missing), provider=request.ref.provider)
        return credential

    @abc.abstractmethod
    async def _get_access_policy(self, request: ConnectionResolutionRequest) -> ConnectionAccessPolicy:
        """Load ownership/opt-in metadata and verify any explicit share, without reading secrets."""

    @abc.abstractmethod
    async def _resolve(
        self, request: ConnectionResolutionRequest, policy: ConnectionAccessPolicy
    ) -> ResolvedCredential:
        """Read/refresh only the connection identified by the authorized policy.

        Hosts must keep policy and credential lookup consistent, using the same
        connection id and checking for ownership/policy changes during resolution.
        """

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
