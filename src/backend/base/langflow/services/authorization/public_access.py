"""Fail-closed authorization for anonymous direct-link flow access.

Anonymous visitors are not users and never enter the authenticated OSS
allow-all authorization path. A request must first match a canonical PUBLIC
``AuthzShare`` or one of the two release-compatibility grants, then (when
authorization is enabled) pass an opt-in plugin tenant and policy decision.
These grants are direct-link only and must never be used by list endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from lfx.log.logger import logger
from lfx.services.authorization import (
    PUBLIC_ANONYMOUS_ACTOR_ID,
    AuthorizationPrincipal,
    PublicAuthorizationRequest,
    PublicResourceAction,
)
from lfx.services.deps import session_scope_readonly
from pydantic import BaseModel, Field
from sqlmodel import select

from langflow.services.authorization.audit import AUDIT_ALLOW, AUDIT_DENY, audit_decision
from langflow.services.authorization.guards import _resolve_authz_domain
from langflow.services.database.models.auth import AuthzShare, ShareScope
from langflow.services.database.models.flow.model import AccessTypeEnum
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_authorization_service, get_settings_service

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow


class PublicGrantSource(str, Enum):
    """Durable or compatibility source of an anonymous direct-link grant."""

    AUTHZ_SHARE = "authz_share"
    LEGACY_ACCESS_TYPE = "legacy_access_type"
    A2A_AUTH_NONE = "a2a_auth_none"


class PublicFlowCapabilities(BaseModel):
    """Anonymous direct-link capabilities for one flow.

    Serialized into direct-link responses so a client renders the actions this
    layer would actually allow, rather than re-deriving them from the legacy
    ``Flow.access_type`` flag.
    """

    can_read: bool = Field(description="Anonymous callers may read this flow at its direct link.")
    can_execute: bool = Field(description="Anonymous callers may run this flow at its direct link.")


_READ_PERMISSIONS = frozenset({"read", "execute", "write", "admin"})
_EXECUTE_PERMISSIONS = frozenset({"execute", "write", "admin"})
PUBLIC_FLOW_NOT_FOUND_DETAIL = "Flow not found"


def public_grant_allows(permission_level: str, action: PublicResourceAction) -> bool:
    """Apply the OSS anonymous action floor to a share permission level.

    Higher share levels retain their read/execute implication, but anonymous
    callers can never mutate, create, delete, deploy, or administer resources.
    """
    if action is PublicResourceAction.READ:
        return permission_level in _READ_PERMISSIONS
    if action is PublicResourceAction.EXECUTE:
        return permission_level in _EXECUTE_PERMISSIONS
    return False


def public_execution_user() -> UserRead:
    """Return the stable non-persisted runtime identity for public execution."""
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return UserRead(
        id=PUBLIC_ANONYMOUS_ACTOR_ID,
        username="anonymous-public",
        profile_image=None,
        store_api_key=None,
        is_active=True,
        is_superuser=False,
        create_at=epoch,
        updated_at=epoch,
        last_login_at=None,
        optins=None,
    )


async def _public_share_permission(session: AsyncSession, flow_id: UUID) -> str | None:
    statement = select(AuthzShare.permission_level).where(
        AuthzShare.resource_type == "flow",
        AuthzShare.resource_id == flow_id,
        AuthzShare.scope == ShareScope.PUBLIC.value,
    )
    return (await session.exec(statement)).first()


async def _resolve_grant(
    *,
    flow: Flow,
    action: PublicResourceAction,
    session: AsyncSession | None,
    compatibility_grant: PublicGrantSource | None,
) -> PublicGrantSource | None:
    if action not in {PublicResourceAction.READ, PublicResourceAction.EXECUTE}:
        return None

    if session is None:
        async with session_scope_readonly() as read_session:
            permission = await _public_share_permission(read_session, flow.id)
    else:
        permission = await _public_share_permission(session, flow.id)

    if permission is not None:
        # A canonical PUBLIC share is authoritative for every anonymous action on
        # this resource. Its level bounds the grant, so a still-set legacy flag
        # cannot widen a read-only share back to execute, and the level the owner
        # chose is the level that is enforced.
        return PublicGrantSource.AUTHZ_SHARE if public_grant_allows(permission, action) else None
    if flow.access_type is AccessTypeEnum.PUBLIC:
        return PublicGrantSource.LEGACY_ACCESS_TYPE
    if compatibility_grant is PublicGrantSource.A2A_AUTH_NONE:
        return PublicGrantSource.A2A_AUTH_NONE
    return None


@dataclass(frozen=True, slots=True)
class _PublicDecision:
    """One resolved anonymous decision, before it is audited or enforced."""

    allowed: bool
    domain: str
    grant_source: str
    tenant: str | None


async def _decide(
    *,
    flow: Flow,
    action: PublicResourceAction,
    principal: AuthorizationPrincipal,
    request_host: str | None,
    compatibility_grant: PublicGrantSource | None,
    session: AsyncSession | None,
) -> _PublicDecision:
    """Resolve the grant and, when authorization is enabled, the policy verdict."""
    source = await _resolve_grant(
        flow=flow,
        action=action,
        session=session,
        compatibility_grant=compatibility_grant,
    )
    domain = _resolve_authz_domain(flow.workspace_id, flow.folder_id)
    request = PublicAuthorizationRequest(
        principal=principal,
        resource_type="flow",
        resource_id=flow.id,
        action=action,
        domain_hint=domain,
        request_host=request_host,
        grant_source=source.value if source is not None else "none",
    )

    allowed = source is not None
    tenant: str | None = None
    auth_settings = get_settings_service().auth_settings
    if allowed and auth_settings.AUTHZ_ENABLED:
        try:
            # Resolving the service is inside the guard on purpose: a service that
            # cannot be constructed must deny like any other policy failure and
            # still record the audit row in the caller, not escape as a 500.
            authorization_service = get_authorization_service()
            if not await authorization_service.supports_public_principals():
                allowed = False
            else:
                tenant = await authorization_service.resolve_public_tenant(request)
                allowed = bool(tenant) and await authorization_service.enforce_public(request, tenant=tenant)
        except Exception:  # noqa: BLE001 - an anonymous policy failure must fail closed
            allowed = False
            await logger.aexception("Anonymous public authorization failed closed for flow %s", flow.id)

    return _PublicDecision(allowed=allowed, domain=domain, grant_source=request.grant_source, tenant=tenant)


async def authorize_public_flow_access(
    *,
    flow: Flow,
    action: PublicResourceAction,
    request_host: str | None = None,
    compatibility_grant: PublicGrantSource | None = None,
    session: AsyncSession | None = None,
) -> AuthorizationPrincipal:
    """Authorize a direct-link flow action and return its anonymous principal.

    The caller must load the exact flow by its direct-link identifier. This
    function never performs tenant discovery and never grants list visibility.

    A canonical PUBLIC share, when present, is the only grant consulted: its
    permission level bounds the action and a still-set legacy flag cannot widen
    it. With no share row, changing ``Flow.access_type``/A2A ``auth_type``
    removes the compatibility grant. New starts and resumes call this function
    again, while already-running work is not interrupted.
    """
    principal = AuthorizationPrincipal.public_anonymous()
    decision = await _decide(
        flow=flow,
        action=action,
        principal=principal,
        request_host=request_host,
        compatibility_grant=compatibility_grant,
        session=session,
    )

    await audit_decision(
        user_id=None,
        principal=principal,
        action=f"flow:{action.value}",
        obj=f"flow:{flow.id}",
        result=AUDIT_ALLOW if decision.allowed else AUDIT_DENY,
        details={
            "domain": decision.domain,
            "grant_source": decision.grant_source,
            **({"tenant": decision.tenant} if decision.tenant is not None else {}),
        },
    )
    if not decision.allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PUBLIC_FLOW_NOT_FOUND_DETAIL)
    return principal


async def public_flow_capabilities(
    *,
    flow: Flow,
    request_host: str | None = None,
    session: AsyncSession | None = None,
) -> PublicFlowCapabilities:
    """Report which anonymous direct-link actions this flow currently permits.

    A direct-link UI needs this because the grant it was admitted by is not
    visible in the flow row: a canonical ``AuthzShare(scope=public)`` authorizes
    a flow whose ``access_type`` is still PRIVATE, and its permission level —
    not the legacy flag — is what bounds execution. Re-deriving public access
    from ``Flow.access_type`` in the client disagrees with this layer in both
    directions, so callers should render from these flags instead.

    Advisory only. It grants nothing: every action still authorizes itself on
    its own request path through :func:`authorize_public_flow_access`. It is
    also deliberately not audited — the visitor is not attempting these actions,
    and emitting a DENY row per page view would turn every read-only share into
    a stream of false anonymous-denial signals for operators.
    """
    principal = AuthorizationPrincipal.public_anonymous()

    async def _allows(action: PublicResourceAction) -> bool:
        decision = await _decide(
            flow=flow,
            action=action,
            principal=principal,
            request_host=request_host,
            compatibility_grant=None,
            session=session,
        )
        return decision.allowed

    return PublicFlowCapabilities(
        can_read=await _allows(PublicResourceAction.READ),
        can_execute=await _allows(PublicResourceAction.EXECUTE),
    )


__all__ = [
    "PUBLIC_ANONYMOUS_ACTOR_ID",
    "PUBLIC_FLOW_NOT_FOUND_DETAIL",
    "PublicFlowCapabilities",
    "PublicGrantSource",
    "PublicResourceAction",
    "authorize_public_flow_access",
    "public_execution_user",
    "public_flow_capabilities",
    "public_grant_allows",
]
