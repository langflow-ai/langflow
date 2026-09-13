"""Canonical resource facts and framework-neutral selected-service delegation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lfx.services.authorization.base import (
    AuthorizationAccessSource as AccessSource,  # noqa: TC002 - compatibility export
)
from sqlalchemy import update
from sqlmodel import col, select

from langflow.services.database.models.auth import (
    AuthzTeam,
    AuthzTeamMember,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True, slots=True)
class ResourceRecord:
    """Server-resolved, non-secret scope for one authorization object."""

    resource_type: str
    resource_id: UUID
    owner_id: UUID | None
    project_id: UUID | None = None
    workspace_id: UUID | None = None
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class EffectiveAccess:
    """Allowed actions and their non-secret provenance."""

    actions: frozenset[str]
    sources: tuple[AccessSource, ...]


@dataclass(frozen=True, slots=True)
class ShareManagementScopes:
    """Compact canonical scopes whose role permits share administration."""

    all_resources: bool = False
    workspace_ids: tuple[UUID, ...] = ()
    project_ids: tuple[UUID, ...] = ()


_MODEL_BY_RESOURCE: dict[str, type[Any]] = {
    "flow": Flow,
    "project": Folder,
    "deployment": Deployment,
    "knowledge_base": KnowledgeBaseRecord,
    "variable": Variable,
    "file": File,
    "provider_account": DeploymentProviderAccount,
}

_RESOURCE_ACTIONS: dict[str, frozenset[str]] = {
    "flow": frozenset({"read", "write", "create", "delete", "execute", "deploy"}),
    "project": frozenset({"read", "write", "create", "delete"}),
    "deployment": frozenset({"read", "write", "create", "delete", "execute"}),
    "knowledge_base": frozenset({"read", "write", "create", "delete", "ingest"}),
    "variable": frozenset({"read", "write", "create", "delete"}),
    "file": frozenset({"read", "write", "create", "delete"}),
    "provider_account": frozenset({"read", "write", "create", "delete"}),
    "voice": frozenset({"read"}),
}


def supported_actions(resource_type: str) -> frozenset[str]:
    """Return the canonical action vocabulary for a resource family."""
    return _RESOURCE_ACTIONS.get(resource_type, frozenset())


async def load_active_user(session: AsyncSession, user_id: UUID) -> User | None:
    """Return a canonical active user, never a request-supplied identity view."""
    user = await session.get(User, user_id, populate_existing=True)
    return user if user is not None and user.is_active is True else None


async def load_resource(
    session: AsyncSession,
    *,
    resource_type: str,
    resource_id: UUID,
    lock: bool = False,
) -> ResourceRecord | None:
    """Resolve one supported resource without loading graph/credential content."""
    model = _MODEL_BY_RESOURCE.get(resource_type)
    if model is None:
        return None
    if lock:
        from langflow.services.deps import get_authorization_service

        await get_authorization_service().acquire_resource_mutation_lock(session=session)
    if lock and session.get_bind().dialect.name == "sqlite":
        # SQLite ignores SELECT FOR UPDATE.  A no-op write establishes its
        # database-wide write transaction before the canonical resource read,
        # matching the ordered parent-row lock used by team mutations.
        await session.exec(update(model).where(model.id == resource_id).values(id=model.id))
    statement = (select(model) if lock else select(*_resource_columns(resource_type, model))).where(
        model.id == resource_id
    )
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    row = (await session.exec(statement)).first()
    if row is None and resource_type == "knowledge_base":
        fallback = (select(MemoryBase) if lock else select(*_resource_columns(resource_type, MemoryBase))).where(
            MemoryBase.id == resource_id
        )
        if lock:
            fallback = fallback.with_for_update()
        row = (await session.exec(fallback)).first()
    if row is None:
        return None
    return _resource_record_from_row(resource_type, row)


def _resource_columns(resource_type: str, model: type[Any]) -> tuple[Any, ...]:
    """Read only canonical scope and display fields, never a graph or credential."""
    if resource_type == "flow":
        return model.id, model.user_id, model.folder_id, model.workspace_id, model.name
    if resource_type == "project":
        return model.id, model.user_id, model.workspace_id, model.name
    if resource_type == "deployment":
        return model.id, model.user_id, model.project_id, model.workspace_id, model.display_name
    return model.id, model.user_id, model.name


def _resource_record_from_row(resource_type: str, row: Any) -> ResourceRecord | None:
    """Project an ORM row into the only non-secret fields policy may use."""
    if resource_type == "flow":
        return ResourceRecord(
            resource_type=resource_type,
            resource_id=row.id,
            owner_id=row.user_id,
            project_id=row.folder_id,
            workspace_id=row.workspace_id,
            display_name=row.name,
        )
    if resource_type == "project":
        return ResourceRecord(
            resource_type=resource_type,
            resource_id=row.id,
            owner_id=row.user_id,
            project_id=row.id,
            workspace_id=row.workspace_id,
            display_name=row.name,
        )
    if resource_type == "deployment":
        return ResourceRecord(
            resource_type=resource_type,
            resource_id=row.id,
            owner_id=row.user_id,
            project_id=row.project_id,
            workspace_id=row.workspace_id,
            display_name=row.display_name,
        )
    if resource_type == "knowledge_base":
        return ResourceRecord(resource_type, row.id, row.user_id, display_name=row.name)
    if resource_type == "variable":
        return ResourceRecord(resource_type, row.id, row.user_id, display_name=row.name)
    if resource_type == "file":
        return ResourceRecord(resource_type, row.id, row.user_id, display_name=row.name)
    if resource_type == "provider_account":
        return ResourceRecord(resource_type, row.id, row.user_id, display_name=row.name)
    return None


async def active_team_ids_for_user(session: AsyncSession, user_id: UUID) -> tuple[UUID, ...]:
    """Return memberships in active teams that still have an active Admin."""
    statement = (
        select(AuthzTeamMember.team_id)
        .join(AuthzTeam, col(AuthzTeam.id) == col(AuthzTeamMember.team_id))
        .join(User, col(User.id) == col(AuthzTeamMember.user_id))
        .where(
            AuthzTeamMember.user_id == user_id,
            AuthzTeam.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
        )
        .order_by(col(AuthzTeamMember.team_id))
    )
    candidate_ids = tuple((await session.exec(statement)).all())
    if not candidate_ids:
        return ()
    valid_ids = set(
        (
            await session.exec(
                select(AuthzTeamMember.team_id)
                .join(User, col(User.id) == col(AuthzTeamMember.user_id))
                .where(
                    col(AuthzTeamMember.team_id).in_(candidate_ids),
                    AuthzTeamMember.role == "admin",
                    User.is_active == True,  # noqa: E712
                )
            )
        ).all()
    )
    return tuple(team_id for team_id in candidate_ids if team_id in valid_ids)


async def invalid_team_ids(session: AsyncSession) -> tuple[UUID, ...]:
    """Return teams that violate the non-empty/active-Admin runtime contract."""
    teams = list((await session.exec(select(AuthzTeam).order_by(col(AuthzTeam.id)))).all())
    if not teams:
        return ()
    members = list(
        (
            await session.exec(
                select(AuthzTeamMember)
                .where(col(AuthzTeamMember.team_id).in_([team.id for team in teams]))
                .order_by(col(AuthzTeamMember.team_id))
            )
        ).all()
    )
    active_user_ids = (
        set(
            (
                await session.exec(
                    select(User.id).where(
                        col(User.id).in_([member.user_id for member in members]),
                        User.is_active == True,  # noqa: E712
                    )
                )
            ).all()
        )
        if members
        else set()
    )
    by_team: dict[UUID, list[AuthzTeamMember]] = {}
    for member in members:
        by_team.setdefault(member.team_id, []).append(member)
    invalid: list[UUID] = []
    for team in teams:
        roster = by_team.get(team.id, [])
        if not roster or (
            team.is_active is True
            and not any(member.role == "admin" and member.user_id in active_user_ids for member in roster)
        ):
            invalid.append(team.id)
    return tuple(invalid)


async def membership_for_team(
    session: AsyncSession,
    *,
    user_id: UUID,
    team_id: UUID,
) -> AuthzTeamMember | None:
    """Load one canonical membership; callers separately validate team state."""
    statement = select(AuthzTeamMember).where(
        AuthzTeamMember.user_id == user_id,
        AuthzTeamMember.team_id == team_id,
    )
    return (await session.exec(statement)).first()


async def share_management_scopes(session: AsyncSession, *, user_id: UUID, action: str) -> ShareManagementScopes:
    """Delegate policy-derived share scopes to the registered service."""
    from lfx.services.authorization.context import authorization_session

    from langflow.services.deps import get_authorization_service

    service = get_authorization_service()
    with authorization_session(session):
        scope = await service.get_resource_visibility(user_id=user_id, resource_type="share", act=action)
    if scope is None:
        return ShareManagementScopes()
    return ShareManagementScopes(scope.all_resources, scope.workspace_ids, scope.project_ids)


async def effective_access(session: AsyncSession, *, user_id: UUID, resource: ResourceRecord) -> EffectiveAccess:
    """Compatibility facade; only the registered service decides and explains access."""
    from lfx.services.authorization.context import authorization_session

    from langflow.services.deps import get_authorization_service

    service = get_authorization_service()
    async with service.admission_context(session=session) as snapshot:
        with authorization_session(snapshot, admission=True):
            permissions = await service.get_effective_permissions(
                user_id=user_id,
                resource_type=resource.resource_type,
                resource_ids=(resource.resource_id,),
                actions=tuple(sorted(supported_actions(resource.resource_type))),
            )
            sources = await service.get_access_sources(
                user_id=user_id, resource_type=resource.resource_type, resource_id=resource.resource_id
            )
    return EffectiveAccess(frozenset(permissions.get(resource.resource_id, ())), sources)


async def user_can_manage_resource_shares(
    session: AsyncSession, *, user: User, resource: ResourceRecord, share_action: str, superuser_bypass: bool
) -> bool:
    """Resolve policy-based share administration at the application service boundary."""
    from lfx.services.authorization.context import authorization_session

    from langflow.services.authorization.access_ceiling import external_access_allows
    from langflow.services.deps import get_authorization_service

    service = get_authorization_service()
    if not await service.is_enabled() or not await service.supports_cross_user_fetch():
        return external_access_allows(share_action) and (
            resource.owner_id == user.id or (user.is_active is True and user.is_superuser is True and superuser_bypass)
        )
    with authorization_session(session):
        return await service.enforce(
            user_id=user.id,
            domain="*",
            obj="share:*",
            act=share_action,
            context={
                "resource_type": resource.resource_type,
                "resource_id": resource.resource_id,
                "share_management_only": True,
            },
        )


async def resource_id_batches(session: AsyncSession, *, resource_type: str) -> AsyncIterator[tuple[UUID, ...]]:
    """Read candidates in bounded keyset batches within the caller's snapshot."""
    model = _MODEL_BY_RESOURCE.get(resource_type)
    if model is None:
        return
    last_id = None
    while True:
        statement = select(model.id).order_by(model.id).limit(200)
        if last_id is not None:
            statement = statement.where(model.id > last_id)
        batch = tuple((await session.exec(statement)).all())
        if not batch:
            return
        yield batch
        last_id = batch[-1]


async def resolve_resources(
    session: AsyncSession,
    *,
    resource_type: str,
    resource_ids: Sequence[UUID],
) -> dict[UUID, ResourceRecord]:
    """Resolve a bounded resource batch without exposing missing IDs."""
    requested = tuple(dict.fromkeys(resource_ids))
    if not requested:
        return {}
    model = _MODEL_BY_RESOURCE.get(resource_type)
    if model is None:
        return {}
    rows = []
    for offset in range(0, len(requested), 200):
        rows.extend(
            (
                await session.exec(
                    select(*_resource_columns(resource_type, model))
                    .where(col(model.id).in_(requested[offset : offset + 200]))
                    .order_by(model.id)
                )
            ).all()
        )
    resolved = {
        row.id: resource for row in rows if (resource := _resource_record_from_row(resource_type, row)) is not None
    }
    if resource_type == "knowledge_base":
        missing = tuple(resource_id for resource_id in requested if resource_id not in resolved)
        if missing:
            fallback_rows = (
                await session.exec(
                    select(*_resource_columns(resource_type, MemoryBase))
                    .where(col(MemoryBase.id).in_(missing))
                    .order_by(col(MemoryBase.id))
                )
            ).all()
            resolved.update(
                {
                    row.id: ResourceRecord("knowledge_base", row.id, row.user_id, display_name=row.name)
                    for row in fallback_rows
                }
            )
    return resolved
