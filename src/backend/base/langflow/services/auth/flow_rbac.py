from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import or_, true
from sqlmodel import col, select

from langflow.services.auth.exceptions import AuthenticationError
from langflow.services.auth.external import extract_external_token, resolve_external_identity
from langflow.services.database.models.flow.model import (
    AccessTypeEnum,
    Flow,
    FlowAccessControl,
    FlowAclSubjectType,
    FlowPermission,
)
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from lfx.services.settings.auth import AuthSettings
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User, UserRead


@dataclass(frozen=True)
class FlowPrincipal:
    user_id: UUID
    is_superuser: bool
    roles: frozenset[str]
    groups: frozenset[str]


_PERMISSION_GRANTS: dict[FlowPermission, set[FlowPermission]] = {
    FlowPermission.VIEW: {FlowPermission.VIEW, FlowPermission.RUN, FlowPermission.EDIT, FlowPermission.MANAGE},
    FlowPermission.RUN: {FlowPermission.RUN, FlowPermission.MANAGE},
    FlowPermission.EDIT: {FlowPermission.EDIT, FlowPermission.MANAGE},
    FlowPermission.MANAGE: {FlowPermission.MANAGE},
}


def _split_csv(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def _claim_values(claims: dict[str, Any], claim_name: str | None) -> frozenset[str]:
    if not claim_name:
        return frozenset()
    value = claims.get(claim_name)
    if value is None:
        return frozenset()
    if isinstance(value, str):
        delimiter = "," if "," in value else None
        return frozenset(item.strip() for item in value.split(delimiter) if item.strip())
    if isinstance(value, (list, tuple, set)):
        return frozenset(str(item).strip() for item in value if str(item).strip())
    return frozenset({str(value).strip()}) if str(value).strip() else frozenset()


async def get_flow_principal(request: Request, user: User | UserRead) -> FlowPrincipal:
    auth_settings = get_settings_service().auth_settings
    roles: frozenset[str] = frozenset()
    groups: frozenset[str] = frozenset()

    token = extract_external_token(request.headers, request.cookies, auth_settings)
    if token:
        try:
            identity = await resolve_external_identity(token, auth_settings)
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.message) from exc
        roles = _claim_values(identity.claims, auth_settings.FLOW_RBAC_ROLE_CLAIM)
        groups = _claim_values(identity.claims, auth_settings.FLOW_RBAC_GROUP_CLAIM)

    return FlowPrincipal(
        user_id=user.id,
        is_superuser=bool(user.is_superuser),
        roles=roles,
        groups=groups,
    )


def is_flow_admin(principal: FlowPrincipal, auth_settings: AuthSettings) -> bool:
    if principal.is_superuser:
        return True
    admin_roles = _split_csv(auth_settings.FLOW_RBAC_ADMIN_ROLES)
    admin_groups = _split_csv(auth_settings.FLOW_RBAC_ADMIN_GROUPS)
    return bool(principal.roles & admin_roles or principal.groups & admin_groups)


def _has_lock_bypass_role(principal: FlowPrincipal, auth_settings: AuthSettings) -> bool:
    bypass_roles = _split_csv(auth_settings.FLOW_RBAC_LOCK_BYPASS_ROLES)
    bypass_groups = _split_csv(auth_settings.FLOW_RBAC_LOCK_BYPASS_GROUPS)
    return bool(principal.roles & bypass_roles or principal.groups & bypass_groups)


def _acl_subject_filter(principal: FlowPrincipal):
    clauses = [
        (FlowAccessControl.subject_type == FlowAclSubjectType.USER.value)
        & (FlowAccessControl.subject_id == str(principal.user_id))
    ]
    if principal.roles:
        clauses.append(
            (FlowAccessControl.subject_type == FlowAclSubjectType.ROLE.value)
            & col(FlowAccessControl.subject_id).in_(principal.roles)
        )
    if principal.groups:
        clauses.append(
            (FlowAccessControl.subject_type == FlowAclSubjectType.GROUP.value)
            & col(FlowAccessControl.subject_id).in_(principal.groups)
        )
    return or_(*clauses)


async def has_explicit_manage_acl(session: AsyncSession, flow_id: UUID, principal: FlowPrincipal) -> bool:
    statement = select(FlowAccessControl.id).where(
        FlowAccessControl.flow_id == flow_id,
        FlowAccessControl.permission == FlowPermission.MANAGE.value,
        _acl_subject_filter(principal),
    )
    return (await session.exec(statement)).first() is not None


async def can_bypass_flow_lock(
    session: AsyncSession,
    flow: Flow,
    principal: FlowPrincipal,
    auth_settings: AuthSettings,
) -> bool:
    if is_flow_admin(principal, auth_settings) or _has_lock_bypass_role(principal, auth_settings):
        return True
    return await has_explicit_manage_acl(session, flow.id, principal)


async def has_flow_permission(
    session: AsyncSession,
    flow: Flow,
    principal: FlowPrincipal,
    permission: FlowPermission,
    auth_settings: AuthSettings | None = None,
) -> bool:
    auth_settings = auth_settings or get_settings_service().auth_settings
    if not auth_settings.FLOW_RBAC_ENABLED:
        return flow.user_id == principal.user_id

    if is_flow_admin(principal, auth_settings):
        return True

    permission_allowed = False
    if flow.user_id == principal.user_id or (
        permission in {FlowPermission.VIEW, FlowPermission.RUN} and flow.access_type == AccessTypeEnum.PUBLIC
    ):
        permission_allowed = True
    else:
        granted_permissions = [item.value for item in _PERMISSION_GRANTS[permission]]
        statement = select(FlowAccessControl.id).where(
            FlowAccessControl.flow_id == flow.id,
            col(FlowAccessControl.permission).in_(granted_permissions),
            _acl_subject_filter(principal),
        )
        permission_allowed = (await session.exec(statement)).first() is not None

    if not permission_allowed:
        return False

    if flow.locked and permission in {FlowPermission.EDIT, FlowPermission.MANAGE}:
        return await can_bypass_flow_lock(session, flow, principal, auth_settings)

    return True


def viewable_flows_filter(principal: FlowPrincipal, auth_settings: AuthSettings):
    if not auth_settings.FLOW_RBAC_ENABLED:
        return Flow.user_id == principal.user_id

    if is_flow_admin(principal, auth_settings):
        return true()

    granted_permissions = [item.value for item in _PERMISSION_GRANTS[FlowPermission.VIEW]]
    acl_subquery = select(FlowAccessControl.flow_id).where(
        col(FlowAccessControl.permission).in_(granted_permissions),
        _acl_subject_filter(principal),
    )
    return or_(
        Flow.user_id == principal.user_id,
        Flow.access_type == AccessTypeEnum.PUBLIC,
        col(Flow.id).in_(acl_subquery),
    )


async def get_flow_by_id_or_name(
    session: AsyncSession,
    flow_id_or_name: str,
) -> Flow | None:
    try:
        flow_id = UUID(flow_id_or_name)
        return await session.get(Flow, flow_id)
    except ValueError:
        statement = select(Flow).where(Flow.endpoint_name == flow_id_or_name)
        return (await session.exec(statement)).first()


async def require_flow_permission(
    session: AsyncSession,
    flow: Flow | None,
    principal: FlowPrincipal,
    permission: FlowPermission,
    *,
    not_found_detail: str = "Flow not found",
) -> Flow:
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)

    if await has_flow_permission(session, flow, principal, permission):
        return flow

    if not await has_flow_permission(session, flow, principal, FlowPermission.VIEW):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission for this flow")
