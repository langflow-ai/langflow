"""Resource-scoped share management, discovery, and access explanations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from lfx.log.logger import logger
from lfx.services.authorization.base import BaseAuthorizationService, ShareRuleSnapshot
from sqlalchemy import and_, exists, or_, true
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas.authz_shares import (
    ShareAccessSourceRead,
    ShareCreate,
    ShareEffectiveAccessRead,
    ShareRead,
    ShareSummaryRead,
    ShareUpdate,
)
from langflow.services.authorization import ShareAction, ensure_resource_share_administration
from langflow.services.authorization.access_ceiling import external_access_allows
from langflow.services.authorization.collaboration import (
    CollaborationCapabilities,
    CollaborationCapabilityError,
    discover_collaboration_capabilities,
)
from langflow.services.authorization.concurrency import strong_etag
from langflow.services.authorization.fetch import authorization_admission, deny_to_404
from langflow.services.authorization.repository import (
    EffectiveAccess,
    ResourceRecord,
    active_team_ids_for_user,
    effective_access,
    load_active_user,
    share_management_scopes,
    user_can_manage_resource_shares,
)
from langflow.services.authorization.share_management import (
    ShareManagementError,
    get_share_for_authorization,
    resolve_resource_for_share,
)
from langflow.services.authorization.share_management import create_share as create_share_transaction
from langflow.services.authorization.share_management import delete_share as delete_share_transaction
from langflow.services.authorization.share_management import update_share as update_share_transaction
from langflow.services.authorization.team_management import actor_can_administer_platform
from langflow.services.authorization.utils import audit_decision
from langflow.services.database.lock_retry import run_with_lock_retry
from langflow.services.database.models.auth import AuthzShare, AuthzTeam, AuthzTeamMember, ShareScope, TeamRole
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.file.model import File as UserFile
from langflow.services.database.models.flow.model import AccessTypeEnum, Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_authorization_service

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/authz/shares", tags=["Authorization"])

_SHARE_POLICY_HOOK_TIMEOUT_SECONDS = 5.0
_LIST_SHARES_MAX_LIMIT = 200
_LIST_SHARES_DEFAULT_LIMIT = 100
_DISPLAY_MODE_BY_PERMISSION = {"read": "read", "execute": "use", "write": "edit", "admin": "admin"}


def _raise_share_error(exc: ShareManagementError) -> NoReturn:
    if exc.code == "SHARE_NOT_FOUND":
        detail: str | dict[str, str] = "Share not found"
    elif exc.code == "SHARE_RESOURCE_NOT_FOUND":
        detail = "Resource not found"
    else:
        detail = exc.detail
    raise HTTPException(status_code=exc.status_code, detail=detail) from exc


def _authorization_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "AUTHORIZATION_NOT_READY", "message": "Authorization is not ready."},
    )


async def _collaboration_contract(*, required: bool) -> CollaborationCapabilities:
    try:
        capabilities = await discover_collaboration_capabilities()
    except CollaborationCapabilityError as exc:
        raise _authorization_unavailable() from exc
    if required and not capabilities.collaboration_ready:
        raise _authorization_unavailable()
    return capabilities


async def _resolve_resource_owner(
    session: DbSession,
    *,
    resource_type: str,
    resource_id: UUID,
) -> UUID | None:
    """Compatibility helper returning the canonical owner when the row exists."""
    try:
        resource = await resolve_resource_for_share(
            session,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    except ShareManagementError:
        if resource_type != "knowledge_base":
            return None
        row = await session.get(MemoryBase, resource_id)
        return row.user_id if row is not None else None
    return resource.owner_id


async def _serialize_shares(session: DbSession, rows: list[AuthzShare]) -> list[ShareRead]:
    """Resolve polymorphic recipient names in two bounded queries."""
    user_ids = {row.target_id for row in rows if row.scope == ShareScope.USER.value and row.target_id is not None}
    team_ids = {row.target_id for row in rows if row.scope == ShareScope.TEAM.value and row.target_id is not None}
    user_names: dict[UUID, str] = {}
    if user_ids:
        result = await session.exec(select(User.id, User.username).where(col(User.id).in_(user_ids)))
        user_names.update(dict(result.all()))
    team_names: dict[UUID, str] = {}
    if team_ids:
        result = await session.exec(select(AuthzTeam.id, AuthzTeam.team_name).where(col(AuthzTeam.id).in_(team_ids)))
        team_names.update(dict(result.all()))

    serialized: list[ShareRead] = []
    for row in rows:
        target_name = None
        if row.scope == ShareScope.USER.value and row.target_id is not None:
            target_name = user_names.get(row.target_id)
        elif row.scope == ShareScope.TEAM.value and row.target_id is not None:
            target_name = team_names.get(row.target_id)
        serialized.append(
            ShareRead.model_validate(row, from_attributes=True).model_copy(
                update={
                    "target_name": target_name,
                    "display_mode": _DISPLAY_MODE_BY_PERMISSION.get(row.permission_level),
                }
            )
        )
    return serialized


def _share_visible(
    *,
    row: AuthzShare,
    user_id: UUID,
    resource_owner_id: UUID | None,
    is_team_member: bool,
) -> bool:
    """Pure recipient/owner visibility rule used by individual reads."""
    if user_id == resource_owner_id:
        return True
    if row.scope == ShareScope.USER.value:
        return row.target_id == user_id
    if row.scope == ShareScope.TEAM.value:
        return row.target_id is not None and is_team_member
    return False


def _active_team_ids_for_user(user_id: UUID):
    admin_membership = aliased(AuthzTeamMember)
    admin_user = aliased(User)
    has_active_admin = exists(
        select(admin_membership.id)
        .join(admin_user, col(admin_user.id) == col(admin_membership.user_id))
        .where(
            col(admin_membership.team_id) == col(AuthzTeamMember.team_id),
            col(admin_membership.role) == TeamRole.ADMIN.value,
            col(admin_user.is_active).is_(True),
        )
    )
    return (
        select(AuthzTeamMember.team_id)
        .join(AuthzTeam, col(AuthzTeam.id) == col(AuthzTeamMember.team_id))
        .join(User, col(User.id) == col(AuthzTeamMember.user_id))
        .where(
            AuthzTeamMember.user_id == user_id,
            AuthzTeam.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            has_active_admin,
        )
    )


async def _user_can_see_share(
    session: DbSession,
    *,
    row: AuthzShare,
    user_id: UUID,
    resource_owner_id: UUID | None,
) -> bool:
    is_team_member = False
    if row.scope == ShareScope.TEAM.value and row.target_id is not None:
        statement = _active_team_ids_for_user(user_id).where(AuthzTeamMember.team_id == row.target_id)
        is_team_member = (await session.exec(statement)).first() is not None
    return _share_visible(
        row=row,
        user_id=user_id,
        resource_owner_id=resource_owner_id,
        is_team_member=is_team_member,
    )


async def _try_bounded_invalidation(operation: Awaitable[None], *, hook_name: str, op: str) -> bool:
    try:
        await asyncio.wait_for(operation, timeout=_SHARE_POLICY_HOOK_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - durable writes already committed
        logger.warning("%s failed after %s; cache may be stale: %s", hook_name, op, exc)
        return False
    return True


async def _invalidate_for_share(scope: str, target_id: UUID | None, *, op: str = "share:write") -> None:
    authz = get_authorization_service()
    if scope == ShareScope.USER.value and target_id is not None:
        if await _try_bounded_invalidation(authz.invalidate_user(target_id), hook_name="invalidate_user", op=op):
            return
        await _try_bounded_invalidation(authz.invalidate_all(), hook_name="invalidate_all fallback", op=op)
        return
    await _try_bounded_invalidation(authz.invalidate_all(), hook_name="invalidate_all", op=op)


def _uses_base_sync_shares(authz: BaseAuthorizationService) -> bool:
    return getattr(type(authz), "sync_shares", None) is BaseAuthorizationService.sync_shares


def _overrides_share_hook(authz: BaseAuthorizationService, hook_name: str) -> bool:
    return getattr(type(authz), hook_name, None) is not getattr(BaseAuthorizationService, hook_name)


async def _try_coarse_share_sync(authz: BaseAuthorizationService, *, op: str) -> bool:
    if _uses_base_sync_shares(authz):
        return False
    try:
        await asyncio.wait_for(authz.sync_shares(), timeout=_SHARE_POLICY_HOOK_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - durable writes already committed
        logger.warning("sync_shares failed after %s; falling back to invalidation: %s", op, exc)
        return False
    return True


async def _refresh_policy_for_share(share_id: UUID, scope: str, target_id: UUID | None, *, op: str) -> None:
    authz = get_authorization_service()
    if _overrides_share_hook(authz, "sync_share"):
        try:
            await asyncio.wait_for(authz.sync_share(share_id), timeout=_SHARE_POLICY_HOOK_TIMEOUT_SECONDS)
        except Exception as exc:  # noqa: BLE001 - durable writes already committed
            logger.warning("sync_share failed after %s; falling back to sync_shares: %s", op, exc)
        else:
            return
    if await _try_coarse_share_sync(authz, op=op):
        return
    await _invalidate_for_share(scope, target_id, op=op)


async def _remove_policy_for_share(snapshot: ShareRuleSnapshot, *, op: str) -> None:
    authz = get_authorization_service()
    if _overrides_share_hook(authz, "remove_share_rules"):
        try:
            await asyncio.wait_for(authz.remove_share_rules(snapshot), timeout=_SHARE_POLICY_HOOK_TIMEOUT_SECONDS)
        except Exception as exc:  # noqa: BLE001 - durable writes already committed
            logger.warning("remove_share_rules failed after %s; falling back to sync_shares: %s", op, exc)
        else:
            return
    if await _try_coarse_share_sync(authz, op=op):
        return
    await _invalidate_for_share(snapshot.scope, snapshot.target_id, op=op)


async def _authorize_resource(
    *,
    current_user: User,
    action: ShareAction,
    resource: ResourceRecord,
    share: AuthzShare | None = None,
    subject_user_id: UUID | None = None,
    audit_session: AsyncSession | None = None,
) -> None:
    try:
        authz = get_authorization_service()
        enforcing_cross_user_policy = await authz.is_enabled() and await authz.supports_cross_user_fetch()
    except Exception as exc:
        raise _authorization_unavailable() from exc

    # Preserve the established enforcement-disabled owner contract.  The
    # generic guard deliberately allows requests while AUTHZ_ENABLED is false,
    # so share administration needs this explicit floor before invoking it.
    # A ready cross-user enforcer becomes authoritative only when it opts into
    # that capability; otherwise a non-owner cannot manufacture a global
    # ``share:*`` permission through the disabled compatibility path.
    if (
        not enforcing_cross_user_policy
        and current_user.id != resource.owner_id
        and not actor_can_administer_platform(current_user)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    try:
        await ensure_resource_share_administration(
            current_user,
            action,
            resource_type=resource.resource_type,
            resource_id=resource.resource_id,
            resource_owner_id=resource.owner_id,
            project_id=resource.project_id,
            workspace_id=resource.workspace_id,
            share_id=share.id if share else None,
            recipient_scope=share.scope if share else None,
            recipient_id=share.target_id if share else None,
            subject_user_id=subject_user_id,
            audit_session=audit_session,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, detail="Resource not found") from exc


def _same_resource(left: ResourceRecord, right: ResourceRecord) -> bool:
    return (
        left.resource_type,
        left.resource_id,
        left.owner_id,
        left.project_id,
        left.workspace_id,
    ) == (
        right.resource_type,
        right.resource_id,
        right.owner_id,
        right.project_id,
        right.workspace_id,
    )


def _resource_exists_predicate() -> ColumnElement[bool]:
    return or_(
        and_(
            col(AuthzShare.resource_type) == "flow",
            exists(select(Flow.id).where(col(Flow.id) == col(AuthzShare.resource_id))),
        ),
        and_(
            col(AuthzShare.resource_type) == "project",
            exists(select(Folder.id).where(col(Folder.id) == col(AuthzShare.resource_id))),
        ),
        and_(
            col(AuthzShare.resource_type) == "deployment",
            exists(select(Deployment.id).where(col(Deployment.id) == col(AuthzShare.resource_id))),
        ),
        and_(
            col(AuthzShare.resource_type) == "knowledge_base",
            or_(
                exists(
                    select(KnowledgeBaseRecord.id).where(col(KnowledgeBaseRecord.id) == col(AuthzShare.resource_id))
                ),
                exists(select(MemoryBase.id).where(col(MemoryBase.id) == col(AuthzShare.resource_id))),
            ),
        ),
        and_(
            col(AuthzShare.resource_type) == "variable",
            exists(select(Variable.id).where(col(Variable.id) == col(AuthzShare.resource_id))),
        ),
        and_(
            col(AuthzShare.resource_type) == "file",
            exists(select(UserFile.id).where(col(UserFile.id) == col(AuthzShare.resource_id))),
        ),
    )


def _owner_predicate(user_id: UUID) -> ColumnElement[bool]:
    return or_(
        and_(
            col(AuthzShare.resource_type) == "flow",
            exists(select(Flow.id).where(col(Flow.id) == col(AuthzShare.resource_id), Flow.user_id == user_id)),
        ),
        and_(
            col(AuthzShare.resource_type) == "project",
            exists(select(Folder.id).where(col(Folder.id) == col(AuthzShare.resource_id), Folder.user_id == user_id)),
        ),
        and_(
            col(AuthzShare.resource_type) == "deployment",
            exists(
                select(Deployment.id).where(
                    col(Deployment.id) == col(AuthzShare.resource_id), Deployment.user_id == user_id
                )
            ),
        ),
        and_(
            col(AuthzShare.resource_type) == "knowledge_base",
            or_(
                exists(
                    select(KnowledgeBaseRecord.id).where(
                        col(KnowledgeBaseRecord.id) == col(AuthzShare.resource_id),
                        KnowledgeBaseRecord.user_id == user_id,
                    )
                ),
                exists(
                    select(MemoryBase.id).where(
                        col(MemoryBase.id) == col(AuthzShare.resource_id),
                        MemoryBase.user_id == user_id,
                    )
                ),
            ),
        ),
        and_(
            col(AuthzShare.resource_type) == "variable",
            exists(
                select(Variable.id).where(col(Variable.id) == col(AuthzShare.resource_id), Variable.user_id == user_id)
            ),
        ),
        and_(
            col(AuthzShare.resource_type) == "file",
            exists(
                select(UserFile.id).where(col(UserFile.id) == col(AuthzShare.resource_id), UserFile.user_id == user_id)
            ),
        ),
    )


async def _management_predicate(session: DbSession, user: User) -> ColumnElement[bool] | None:
    if actor_can_administer_platform(user):
        return true()

    scopes = await share_management_scopes(session, user_id=user.id, action="read")
    if scopes.all_resources:
        return true()
    predicates: list[ColumnElement[bool]] = []
    if scopes.workspace_ids:
        workspace_ids = scopes.workspace_ids
        predicates.extend(
            (
                and_(
                    col(AuthzShare.resource_type) == "flow",
                    exists(
                        select(Flow.id).where(
                            col(Flow.id) == col(AuthzShare.resource_id),
                            col(Flow.workspace_id).in_(workspace_ids),
                        )
                    ),
                ),
                and_(
                    col(AuthzShare.resource_type) == "project",
                    exists(
                        select(Folder.id).where(
                            col(Folder.id) == col(AuthzShare.resource_id),
                            col(Folder.workspace_id).in_(workspace_ids),
                        )
                    ),
                ),
                and_(
                    col(AuthzShare.resource_type) == "deployment",
                    exists(
                        select(Deployment.id).where(
                            col(Deployment.id) == col(AuthzShare.resource_id),
                            col(Deployment.workspace_id).in_(workspace_ids),
                        )
                    ),
                ),
            )
        )
    if scopes.project_ids:
        project_ids = scopes.project_ids
        predicates.extend(
            (
                and_(col(AuthzShare.resource_type) == "project", col(AuthzShare.resource_id).in_(project_ids)),
                and_(
                    col(AuthzShare.resource_type) == "flow",
                    exists(
                        select(Flow.id).where(
                            col(Flow.id) == col(AuthzShare.resource_id),
                            col(Flow.folder_id).in_(project_ids),
                        )
                    ),
                ),
                and_(
                    col(AuthzShare.resource_type) == "deployment",
                    exists(
                        select(Deployment.id).where(
                            col(Deployment.id) == col(AuthzShare.resource_id),
                            col(Deployment.project_id).in_(project_ids),
                        )
                    ),
                ),
            )
        )
    return or_(*predicates) if predicates else None


async def _share_visibility_predicate(session: DbSession, user: User) -> ColumnElement[bool]:
    recipient = or_(
        and_(col(AuthzShare.scope) == ShareScope.USER.value, col(AuthzShare.target_id) == user.id),
        and_(
            col(AuthzShare.scope) == ShareScope.TEAM.value,
            col(AuthzShare.target_id).in_(_active_team_ids_for_user(user.id)),
        ),
    )
    visible = [_owner_predicate(user.id), recipient]
    management = await _management_predicate(session, user)
    if management is not None:
        visible.append(management)
    return and_(_resource_exists_predicate(), or_(*visible))


@router.post("", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
async def create_share(payload: ShareCreate, current_user: CurrentActiveUser, session: DbSession) -> ShareRead:
    """Create one canonical grant after resource and recipient authorization."""
    await _collaboration_contract(required=payload.scope in {ShareScope.USER.value, ShareScope.TEAM.value})

    async def operation(_attempt: int):
        await get_authorization_service().acquire_share_mutation_lock(session=session)
        # A SQLite lock retry starts a fresh transaction. Re-resolve and
        # re-authorize here so neither the policy snapshot nor a durable
        # decision row belongs to the transaction that was rolled back.
        try:
            resource = await resolve_resource_for_share(
                session,
                resource_type=payload.resource_type,
                resource_id=payload.resource_id,
            )
        except ShareManagementError as exc:
            _raise_share_error(exc)
        await _authorize_resource(
            current_user=current_user,
            action=ShareAction.CREATE,
            resource=resource,
            audit_session=session,
        )
        result = await create_share_transaction(
            session,
            actor_id=current_user.id,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            scope=payload.scope,
            target_id=payload.target_id,
            permission_level=payload.permission_level,
        )
        if not _same_resource(resource, result.resource):
            raise ShareManagementError(
                status_code=409,
                code="SHARE_RESOURCE_CHANGED",
                message="The resource changed while the share was being created.",
            )
        return result

    try:
        result = await run_with_lock_retry(operation, session=session, description="create share")
        await session.commit()
    except ShareManagementError as exc:
        await session.rollback()
        _raise_share_error(exc)
    await session.refresh(result.row)
    serialized = (await _serialize_shares(session, [result.row]))[0]
    await _refresh_policy_for_share(serialized.id, serialized.scope, serialized.target_id, op="share:create")
    return serialized


@router.get("", response_model=list[ShareRead])
@router.get("/", response_model=list[ShareRead])
async def list_shares(
    current_user: CurrentActiveUser,
    session: DbSession,
    resource_type: Annotated[str | None, Query()] = None,
    resource_id: Annotated[UUID | None, Query()] = None,
    target_id: Annotated[UUID | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_LIST_SHARES_MAX_LIMIT)] = _LIST_SHARES_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ShareRead]:
    """List only rows visible to the caller, filtered before pagination."""
    async with authorization_admission(session) as admission:
        actor = await load_active_user(admission, current_user.id)
        if actor is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        statement = select(AuthzShare).where(await _share_visibility_predicate(admission, actor))
        if resource_type is not None:
            statement = statement.where(col(AuthzShare.resource_type) == resource_type)
        if resource_id is not None:
            statement = statement.where(col(AuthzShare.resource_id) == resource_id)
        if target_id is not None:
            statement = statement.where(col(AuthzShare.target_id) == target_id)
        if scope is not None:
            try:
                scope = ShareScope(scope).value
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Unknown scope {scope!r}") from exc
            statement = statement.where(col(AuthzShare.scope) == scope)
        statement = (
            statement.order_by(col(AuthzShare.created_at).desc(), col(AuthzShare.id)).offset(offset).limit(limit)
        )
        return await _serialize_shares(admission, list((await admission.exec(statement)).all()))


def _serialize_access_sources(access: EffectiveAccess, *, expose_identifiers: bool) -> list[ShareAccessSourceRead]:
    return [
        ShareAccessSourceRead(
            kind=source.kind,
            actions=list(source.actions),
            source_id=source.source_id if expose_identifiers else None,
            label=source.label if expose_identifiers else None,
        )
        for source in access.sources
    ]


@router.get("/summary", response_model=ShareSummaryRead)
async def get_share_summary(
    current_user: CurrentActiveUser,
    session: DbSession,
    resource_type: Annotated[Literal["flow", "project"], Query()],
    resource_id: Annotated[UUID, Query()],
    subject_user_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_LIST_SHARES_MAX_LIMIT)] = _LIST_SHARES_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ShareSummaryRead:
    """Return bounded direct grants and effective access for one subject."""
    async with authorization_admission(session) as admission:
        await _collaboration_contract(required=True)
        try:
            resource = await resolve_resource_for_share(
                admission,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        except ShareManagementError as exc:
            _raise_share_error(exc)
        subject_id = subject_user_id or current_user.id
        await _authorize_resource(
            current_user=current_user,
            action=ShareAction.READ,
            resource=resource,
            subject_user_id=subject_id,
        )
        actor = await load_active_user(admission, current_user.id)
        subject = await load_active_user(admission, subject_id)
        if actor is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        if subject is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        can_manage = external_access_allows(ShareAction.CREATE.value) and await user_can_manage_resource_shares(
            admission,
            user=actor,
            resource=resource,
            share_action=ShareAction.CREATE.value,
            superuser_bypass=actor_can_administer_platform(actor),
        )
        if subject_id != actor.id and not can_manage:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

        grants = select(AuthzShare).where(
            col(AuthzShare.resource_type) == resource.resource_type,
            col(AuthzShare.resource_id) == resource.resource_id,
        )
        if not can_manage:
            team_ids = await active_team_ids_for_user(admission, subject_id)
            predicates = [and_(col(AuthzShare.scope) == ShareScope.USER.value, col(AuthzShare.target_id) == subject_id)]
            if team_ids:
                predicates.append(
                    and_(col(AuthzShare.scope) == ShareScope.TEAM.value, col(AuthzShare.target_id).in_(team_ids))
                )
            grants = grants.where(or_(*predicates))
        rows = list(
            (
                await admission.exec(
                    grants.order_by(col(AuthzShare.created_at).desc(), col(AuthzShare.id))
                    .offset(offset)
                    .limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        access = await effective_access(admission, user_id=subject_id, resource=resource)
        inherited = any(source.kind.startswith("inherited_") for source in access.sources)
        additional_warning = None
        if len(access.sources) > 1:
            additional_warning = "Additional access sources may remain after one grant is changed or removed."
        legacy_public = False
        if can_manage and resource.resource_type == "flow":
            flow = await admission.get(Flow, resource.resource_id)
            legacy_public = flow is not None and flow.access_type == AccessTypeEnum.PUBLIC
        administrative = any(source.kind == "role" or "delete" in source.actions for source in access.sources)
        return ShareSummaryRead(
            resource_type=cast("Literal['flow', 'project']", resource.resource_type),
            resource_id=resource.resource_id,
            display_name=resource.display_name,
            subject_user_id=subject_id,
            caller_is_owner=resource.owner_id == actor.id,
            can_manage_shares=can_manage,
            direct_grants=await _serialize_shares(admission, rows),
            effective_access=ShareEffectiveAccessRead(
                actions=sorted(access.actions),
                sources=_serialize_access_sources(access, expose_identifiers=can_manage),
            ),
            inherited_from_project=inherited,
            additional_access_warning=additional_warning,
            legacy_public_access=legacy_public,
            administrative_grant_present=administrative,
            has_more=has_more,
            next_offset=offset + limit if has_more else None,
        )


@router.get("/{share_id}", response_model=ShareRead)
async def get_share(
    share_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    response: Response,
) -> ShareRead:
    async with authorization_admission(session) as admission:
        try:
            row, resource = await get_share_for_authorization(admission, share_id)
        except ShareManagementError as exc:
            _raise_share_error(exc)
        await _authorize_resource(current_user=current_user, action=ShareAction.READ, resource=resource, share=row)
        if not await _user_can_see_share(
            admission,
            row=row,
            user_id=current_user.id,
            resource_owner_id=resource.owner_id,
        ):
            actor = await load_active_user(admission, current_user.id)
            if actor is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
            if not await user_can_manage_resource_shares(
                admission,
                user=actor,
                resource=resource,
                share_action=ShareAction.READ.value,
                superuser_bypass=actor_can_administer_platform(actor),
            ):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
        serialized = (await _serialize_shares(admission, [row]))[0]
        response.headers["ETag"] = strong_etag("share", row.id, row.revision)
        return serialized


@router.patch("/{share_id}", response_model=ShareRead)
async def update_share(
    share_id: UUID,
    payload: ShareUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ShareRead:
    try:
        stored, _ = await get_share_for_authorization(session, share_id)
    except ShareManagementError as exc:
        _raise_share_error(exc)
    contract = await _collaboration_contract(required=stored.scope in {ShareScope.USER.value, ShareScope.TEAM.value})

    async def operation(_attempt: int):
        await get_authorization_service().acquire_share_mutation_lock(session=session)
        try:
            current_share, resource = await get_share_for_authorization(session, share_id)
        except ShareManagementError as exc:
            _raise_share_error(exc)
        await _authorize_resource(
            current_user=current_user,
            action=ShareAction.UPDATE,
            resource=resource,
            share=current_share,
            audit_session=session,
        )
        result = await update_share_transaction(
            session,
            actor_id=current_user.id,
            share_id=share_id,
            permission_level=payload.permission_level,
            if_match=if_match,
            precondition_required=contract.conditional_writes_required,
        )
        if not _same_resource(resource, result.resource):
            raise ShareManagementError(
                status_code=409,
                code="SHARE_RESOURCE_CHANGED",
                message="The resource changed while the share was being updated.",
            )
        return result

    try:
        result = await run_with_lock_retry(operation, session=session, description=f"update share {share_id}")
        await session.commit()
    except ShareManagementError as exc:
        await session.rollback()
        _raise_share_error(exc)
    await session.refresh(result.row)
    serialized = (await _serialize_shares(session, [result.row]))[0]
    response.headers["ETag"] = strong_etag("share", result.row.id, result.row.revision)
    if result.changed:
        await _refresh_policy_for_share(result.row.id, result.row.scope, result.row.target_id, op="share:update")
    return serialized


@router.delete("/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_share(
    share_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> None:
    try:
        stored, _ = await get_share_for_authorization(session, share_id)
    except ShareManagementError as exc:
        _raise_share_error(exc)
    contract = await _collaboration_contract(required=stored.scope in {ShareScope.USER.value, ShareScope.TEAM.value})

    async def operation(_attempt: int):
        await get_authorization_service().acquire_share_mutation_lock(session=session)
        try:
            current_share, resource = await get_share_for_authorization(session, share_id)
        except ShareManagementError as exc:
            _raise_share_error(exc)
        await _authorize_resource(
            current_user=current_user,
            action=ShareAction.DELETE,
            resource=resource,
            share=current_share,
            audit_session=session,
        )
        result = await delete_share_transaction(
            session,
            actor_id=current_user.id,
            share_id=share_id,
            if_match=if_match,
            precondition_required=contract.conditional_writes_required,
        )
        if not _same_resource(resource, result.resource):
            raise ShareManagementError(
                status_code=409,
                code="SHARE_RESOURCE_CHANGED",
                message="The resource changed while the share was being removed.",
            )
        return result

    try:
        result = await run_with_lock_retry(operation, session=session, description=f"delete share {share_id}")
        await session.commit()
    except ShareManagementError as exc:
        await session.rollback()
        _raise_share_error(exc)
    await _remove_policy_for_share(result.snapshot, op="share:delete")


__all__ = ["audit_decision", "router"]
