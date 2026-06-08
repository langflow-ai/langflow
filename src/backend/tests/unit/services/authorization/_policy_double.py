"""In-test authorization enforcer for OSS RBAC integration tests.

The OSS :class:`LangflowAuthorizationService` is a pass-through: ``enforce()``
always returns ``True`` and ``SUPPORTS_CROSS_USER_FETCH`` is ``False``. That makes
it impossible to assert allow/deny semantics against the real routes — every
request is allowed and cross-user fetch never widens. This module supplies a
minimal, dependency-free stand-in that derives allow/deny from the seeded
``authz_role`` / ``authz_role_assignment`` / ``authz_share`` rows. It is enough
to validate that the OSS guard wiring, domain resolution, share-aware fetch, and
``deny_to_404`` masking behave correctly under a *real* allow/deny signal —
without pulling in the EE Casbin package.

Install it for the duration of a test with :func:`install_policy_authz`, which
swaps the service registered on the service manager so every
``get_authorization_service()`` call site (guards, fetch, listing, helpers) sees
it, and flips ``AUTHZ_ENABLED=True`` / ``AUTHZ_SUPERUSER_BYPASS=False``.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langflow.services.database.models.auth import AuthzRole, AuthzRoleAssignment, AuthzShare
from lfx.services.authorization.base import BaseAuthorizationService
from sqlmodel import col, select

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession

# Actions granted by each AuthzShare.permission_level. ``write`` and ``execute``
# are independent (each grants ``read`` plus itself); ``admin`` grants the lot.
# Mirrors SharePermissionLevel without baking a questionable write<execute order.
_SHARE_LEVEL_ACTIONS: dict[str, frozenset[str]] = {
    "read": frozenset({"read"}),
    "write": frozenset({"read", "write"}),
    "execute": frozenset({"read", "execute"}),
    "admin": frozenset({"read", "write", "execute", "create", "delete", "deploy", "update", "share"}),
}

# Built-in role permission sets — mirrors migration 7c8d9e0f1a2b_authz_foundations
# so the test does not depend on whether the test DB ran the seed step.
_VIEWER: tuple[str, ...] = (
    "flow:read",
    "flow:execute",
    "deployment:read",
    "project:read",
    "knowledge_base:read",
    "variable:read",
    "file:read",
)
_DEVELOPER_EXTRA: tuple[str, ...] = (
    "flow:write",
    "flow:create",
    "deployment:write",
    "deployment:create",
    "deployment:execute",
    "project:write",
    "project:create",
    "knowledge_base:write",
    "knowledge_base:create",
    "knowledge_base:ingest",
    "variable:write",
    "variable:create",
    "file:write",
    "file:create",
)
_ADMIN_EXTRA: tuple[str, ...] = (
    "flow:delete",
    "flow:deploy",
    "deployment:delete",
    "project:delete",
    "knowledge_base:delete",
    "variable:delete",
    "file:delete",
    "share:read",
    "share:create",
    "share:update",
    "share:delete",
)
SYSTEM_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "viewer": list(_VIEWER),
    "developer": list(_VIEWER + _DEVELOPER_EXTRA),
    "admin": list(_VIEWER + _DEVELOPER_EXTRA + _ADMIN_EXTRA),
}


class PolicyTestAuthorizationService(BaseAuthorizationService):
    """Allow/deny enforcer backed by the authz_* policy tables (test-only).

    A request is allowed when the user holds a role (covering the request domain)
    whose permissions include ``{resource}:{action}``, OR when an ``authz_share``
    row grants the action on the specific resource. Superusers bypass only when
    ``AUTHZ_SUPERUSER_BYPASS`` is set.
    """

    SUPPORTS_CROSS_USER_FETCH = True

    def __init__(self, settings_service: SettingsService) -> None:
        super().__init__()
        self.settings_service = settings_service
        self.set_ready()

    async def is_enabled(self) -> bool:
        return bool(self.settings_service.auth_settings.AUTHZ_ENABLED)

    async def enforce(
        self,
        *,
        user_id: UUID,
        domain: str,
        obj: str,
        act: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        auth_settings = self.settings_service.auth_settings
        if context and context.get("is_superuser") and getattr(auth_settings, "AUTHZ_SUPERUSER_BYPASS", False):
            return True

        resource_type, _, resource_id_str = obj.partition(":")
        # Each enforce opens its own session — a real plugin reads policy from its
        # own connection, independent of the request's transaction.
        from langflow.services.deps import session_scope

        async with session_scope() as session:
            if await self._role_allows(session, user_id, domain, resource_type, act):
                return True
            if resource_id_str and resource_id_str != "*":
                with contextlib.suppress(ValueError):
                    resource_id = UUID(str(resource_id_str))
                    if await self._share_allows(session, resource_id, user_id, resource_type, act):
                        return True
        return False

    async def batch_enforce(
        self,
        *,
        user_id: UUID,
        domain: str,
        requests: Sequence[tuple[str, str]],
        context: dict[str, Any] | None = None,
    ) -> list[bool]:
        return [
            await self.enforce(user_id=user_id, domain=domain, obj=obj, act=act, context=context)
            for obj, act in requests
        ]

    async def _role_allows(
        self,
        session: AsyncSession,
        user_id: UUID,
        domain: str,
        resource_type: str,
        act: str,
    ) -> bool:
        assignments = (
            await session.exec(select(AuthzRoleAssignment).where(AuthzRoleAssignment.user_id == user_id))
        ).all()
        role_ids = [a.role_id for a in assignments if _assignment_covers(a, domain)]
        if not role_ids:
            return False
        roles = (await session.exec(select(AuthzRole).where(col(AuthzRole.id).in_(role_ids)))).all()
        needed = f"{resource_type}:{act}"
        wildcard = f"{resource_type}:*"
        return any(
            needed in (role.permissions or [])
            or wildcard in (role.permissions or [])
            or "*:*" in (role.permissions or [])
            for role in roles
        )

    async def _share_allows(
        self,
        session: AsyncSession,
        resource_id: UUID,
        user_id: UUID,
        resource_type: str,
        act: str,
    ) -> bool:
        shares = (
            await session.exec(
                select(AuthzShare).where(
                    AuthzShare.resource_type == resource_type,
                    AuthzShare.resource_id == resource_id,
                )
            )
        ).all()
        for share in shares:
            if not _share_targets_user(share, user_id):
                continue
            if act in _SHARE_LEVEL_ACTIONS.get(share.permission_level, frozenset()):
                return True
        return False


def _assignment_covers(assignment: AuthzRoleAssignment, request_domain: str) -> bool:
    """A global assignment covers every domain; a scoped one must match exactly.

    The scoped form is intentionally exact (``{domain_type}:{domain_id}`` ==
    request domain) so a regression that changes the domain the route resolves
    flips the decision and trips the test.
    """
    if assignment.domain_type == "global" or assignment.domain_id is None:
        return True
    return f"{assignment.domain_type}:{assignment.domain_id}" == request_domain


def _share_targets_user(share: AuthzShare, user_id: UUID) -> bool:
    if share.scope == "public":
        return True
    if share.scope == "user":
        return str(share.target_id) == str(user_id)
    # team scope would need a membership lookup; unused by the current tests.
    return False


# --------------------------------------------------------------------------- #
# Seeding helpers — write policy rows the enforcer reads.
# --------------------------------------------------------------------------- #


async def seed_system_roles(session: AsyncSession) -> dict[str, UUID]:
    """Get-or-create viewer/developer/admin roles; return ``{name: role_id}``."""
    ids: dict[str, UUID] = {}
    for name, permissions in SYSTEM_ROLE_PERMISSIONS.items():
        existing = (await session.exec(select(AuthzRole).where(AuthzRole.name == name))).first()
        if existing is None:
            existing = AuthzRole(
                name=name, description=f"{name} (test seed)", is_system=True, permissions=list(permissions)
            )
            session.add(existing)
            await session.flush()
        ids[name] = existing.id
    await session.commit()
    return ids


async def assign_role(
    session: AsyncSession,
    *,
    user_id: UUID,
    role_id: UUID,
    domain_type: str = "global",
    domain_id: UUID | None = None,
) -> None:
    """Bind ``user_id`` to ``role_id`` within an optional domain."""
    session.add(AuthzRoleAssignment(user_id=user_id, role_id=role_id, domain_type=domain_type, domain_id=domain_id))
    await session.commit()


async def create_user_share(
    session: AsyncSession,
    *,
    resource_type: str,
    resource_id: UUID,
    target_user_id: UUID,
    permission_level: str,
    created_by: UUID,
) -> AuthzShare:
    """Create a ``scope='user'`` AuthzShare granting ``target_user_id`` access."""
    share = AuthzShare(
        resource_type=resource_type,
        resource_id=resource_id,
        scope="user",
        target_id=target_user_id,
        permission_level=permission_level,
        created_by=created_by,
    )
    session.add(share)
    await session.commit()
    return share


@contextlib.contextmanager
def install_policy_authz(settings_service: SettingsService) -> Iterator[PolicyTestAuthorizationService]:
    """Install the policy test-double + enable enforcement for the block; restore on exit.

    Swaps the cached authorization service on the service manager (string-enum
    keys make ``ServiceType.AUTHORIZATION_SERVICE`` interchangeable across the
    lfx/langflow enums) so every ``get_authorization_service()`` resolves to the
    double, and flips the auth settings the guards read.
    """
    from langflow.services.schema import ServiceType
    from lfx.services.manager import get_service_manager

    auth_settings = settings_service.auth_settings
    saved_enabled = auth_settings.AUTHZ_ENABLED
    saved_bypass = auth_settings.AUTHZ_SUPERUSER_BYPASS

    service_manager = get_service_manager()
    previous_service = service_manager.services.get(ServiceType.AUTHORIZATION_SERVICE)

    auth_settings.AUTHZ_ENABLED = True
    auth_settings.AUTHZ_SUPERUSER_BYPASS = False
    double = PolicyTestAuthorizationService(settings_service)
    service_manager.services[ServiceType.AUTHORIZATION_SERVICE] = double
    try:
        yield double
    finally:
        if previous_service is not None:
            service_manager.services[ServiceType.AUTHORIZATION_SERVICE] = previous_service
        else:
            service_manager.services.pop(ServiceType.AUTHORIZATION_SERVICE, None)
        auth_settings.AUTHZ_ENABLED = saved_enabled
        auth_settings.AUTHZ_SUPERUSER_BYPASS = saved_bypass
