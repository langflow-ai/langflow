"""CRUD API for authz_share rows (enforcement is delegated to authorization plugins)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from lfx.log.logger import logger
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas.authz_shares import ShareCreate, ShareRead, ShareUpdate
from langflow.services.authorization import ShareAction, ensure_share_permission
from langflow.services.authorization.utils import audit_decision
from langflow.services.database.models.auth import AuthzShare, AuthzTeamMember, SharePermissionLevel, ShareScope
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.file.model import File as UserFile
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_authorization_service

router = APIRouter(prefix="/authz/shares", tags=["Authorization"])


# resource_type slug → (model, owner column).
_RESOURCE_OWNER_LOOKUPS: dict[str, tuple[type, str]] = {
    "flow": (Flow, "user_id"),
    "deployment": (Deployment, "user_id"),
    "project": (Folder, "user_id"),
    "knowledge_base": (KnowledgeBaseRecord, "user_id"),
    "variable": (Variable, "user_id"),
    "file": (UserFile, "user_id"),
}


async def _resolve_resource_owner(
    session: DbSession,
    *,
    resource_type: str,
    resource_id: UUID,
) -> UUID | None:
    """Return the owner ``user_id`` for the named resource, or None if not found."""
    lookup = _RESOURCE_OWNER_LOOKUPS.get(resource_type)
    if lookup is None:
        return None
    model, owner_attr = lookup
    row = await session.get(model, resource_id)
    if row is None:
        return None
    return getattr(row, owner_attr, None)


def _share_visible(
    *,
    row: AuthzShare,
    user_id: UUID,
    resource_owner_id: UUID | None,
    is_team_member: bool,
) -> bool:
    """Pure visibility predicate shared by the single-row and list paths.

    ``is_team_member`` is resolved by the caller — a membership query for the
    single-row path, a pre-fetched team-id set for the list path — so this
    predicate stays free of I/O and the owner/PUBLIC/USER/TEAM rules live in one
    place.
    """
    if user_id in {resource_owner_id, row.created_by}:
        return True
    scope = row.scope
    if scope == ShareScope.PUBLIC.value:
        return True
    if scope == ShareScope.USER.value and row.target_id == user_id:
        return True
    if scope == ShareScope.TEAM.value and row.target_id is not None:
        return is_team_member
    return False


async def _user_can_see_share(
    session: DbSession,
    *,
    row: AuthzShare,
    user_id: UUID,
    resource_owner_id: UUID | None,
) -> bool:
    """Return True when the user may see this share row (single-row path)."""
    is_team_member = False
    if row.scope == ShareScope.TEAM.value and row.target_id is not None:
        membership_stmt = select(AuthzTeamMember).where(
            AuthzTeamMember.team_id == row.target_id,
            AuthzTeamMember.user_id == user_id,
        )
        is_team_member = (await session.exec(membership_stmt)).first() is not None
    return _share_visible(
        row=row,
        user_id=user_id,
        resource_owner_id=resource_owner_id,
        is_team_member=is_team_member,
    )


async def _invalidate_for_share(scope: str, target_id: UUID | None) -> None:
    """Invalidate cached policy after a share write (user scope vs invalidate_all)."""
    authz = get_authorization_service()
    if scope == ShareScope.USER.value and target_id is not None:
        await authz.invalidate_user(target_id)
    else:
        await authz.invalidate_all()


async def _ensure_can_administer_share(
    *,
    user: User,
    owner_id: UUID | None,
) -> None:
    """Require resource owner or superuser unless cross-user enforcement is active."""
    if getattr(user, "is_superuser", False):
        return
    if owner_id is not None and owner_id == user.id:
        return
    authz = get_authorization_service()
    if await authz.supports_cross_user_fetch() and await authz.is_enabled():
        # Why: in OSS, ``supports_cross_user_fetch()`` is False (see
        # LangflowAuthorizationService), so this early-return is dead and the
        # explicit 403 below is the floor. When an authorization plugin signals
        # cross-user fetch support, the plugin is the authoritative gate via
        # the ``ensure_share_permission()`` call that every share route makes
        # immediately after this helper. Removing that downstream call — or
        # weakening the plugin's cross-user fetch contract — REOPENS the
        # ownership gap. Keep the two in lockstep.
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the resource owner or a superuser may administer shares for this resource.",
    )


@router.post("", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
async def create_share(
    payload: ShareCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ShareRead:
    """Create an authz_share row for a resource."""
    owner_id = await _resolve_resource_owner(
        session,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
    )
    if owner_id is None:
        # UUID privacy: missing resource → 404.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    await _ensure_can_administer_share(user=current_user, owner_id=owner_id)
    # SECURITY: pass the *resource* owner (not the caller) so the owner-override
    # in ensure_share_permission only fast-paths the real resource owner. With
    # share_user_id=current_user.id the override would always trip and the
    # authorization plugin's enforce() would never run for non-owner creators
    # when the OSS floor is bypassed (cross_user_fetch + AUTHZ_ENABLED).
    await ensure_share_permission(
        current_user,
        ShareAction.CREATE,
        share_user_id=owner_id,
    )

    row = AuthzShare(
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        scope=payload.scope,
        target_id=payload.target_id,
        permission_level=payload.permission_level,
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    try:
        await session.flush()
    except Exception as exc:
        # Log server-side; return a fixed 409 message (no schema leakage).
        await session.rollback()
        logger.warning("authz_share insert rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Share could not be created: it may already exist or conflict with an existing share.",
        ) from exc
    await session.refresh(row)

    # Invalidate policy cache for the share audience.
    await _invalidate_for_share(payload.scope, payload.target_id)

    await audit_decision(
        user_id=current_user.id,
        action="share:create",
        obj=f"{payload.resource_type}:{payload.resource_id}",
        result="allow",
        details={
            "share_id": str(row.id),
            "scope": payload.scope,
            "target_id": str(payload.target_id) if payload.target_id else None,
            "permission_level": payload.permission_level,
        },
    )
    return ShareRead.model_validate(row, from_attributes=True)


_LIST_SHARES_MAX_LIMIT = 200
_LIST_SHARES_DEFAULT_LIMIT = 100


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
    """List share rows visible to the caller (paginated, max 200)."""
    await ensure_share_permission(
        current_user,
        ShareAction.READ,
        share_user_id=current_user.id,
    )

    stmt = select(AuthzShare)
    if resource_type is not None:
        stmt = stmt.where(AuthzShare.resource_type == resource_type)
    if resource_id is not None:
        stmt = stmt.where(AuthzShare.resource_id == resource_id)
    if target_id is not None:
        stmt = stmt.where(AuthzShare.target_id == target_id)
    if scope is not None:
        # Reject unknown scope values early (422).
        try:
            scope_value = ShareScope(scope).value
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Unknown scope {scope!r}") from exc
        stmt = stmt.where(AuthzShare.scope == scope_value)

    # Stable ordering with offset/limit pagination.
    stmt = stmt.order_by(AuthzShare.created_at.desc(), AuthzShare.id).offset(offset).limit(limit)

    rows = list(await session.exec(stmt))

    is_superuser = getattr(current_user, "is_superuser", False)
    if is_superuser:
        return [ShareRead.model_validate(row, from_attributes=True) for row in rows]

    # Pre-fetch team memberships (avoid N+1 per row).
    team_membership_stmt = select(AuthzTeamMember.team_id).where(AuthzTeamMember.user_id == current_user.id)
    caller_team_ids: set[UUID] = set(await session.exec(team_membership_stmt))

    # Filter rows by visibility rules for non-superusers.
    visible: list[ShareRead] = []
    owner_cache: dict[tuple[str, UUID], UUID | None] = {}
    for row in rows:
        key = (row.resource_type, row.resource_id)
        if key not in owner_cache:
            owner_cache[key] = await _resolve_resource_owner(
                session,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
            )
        if _row_visible_to(
            row=row,
            user_id=current_user.id,
            resource_owner_id=owner_cache[key],
            caller_team_ids=caller_team_ids,
        ):
            visible.append(ShareRead.model_validate(row, from_attributes=True))
    return visible


def _row_visible_to(
    *,
    row: AuthzShare,
    user_id: UUID,
    resource_owner_id: UUID | None,
    caller_team_ids: set[UUID],
) -> bool:
    """Batch list visibility check using pre-fetched team ids."""
    is_team_member = row.target_id is not None and row.target_id in caller_team_ids
    return _share_visible(
        row=row,
        user_id=user_id,
        resource_owner_id=resource_owner_id,
        is_team_member=is_team_member,
    )


@router.get("/{share_id}", response_model=ShareRead)
async def get_share(
    share_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ShareRead:
    """Fetch a single share by id with the same visibility rules as list."""
    row = await session.get(AuthzShare, share_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")

    owner_id = await _resolve_resource_owner(
        session,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
    )
    # See create_share: owner_id is the *resource* owner so non-owners are
    # forced through ensure_share_permission's plugin enforce() path.
    await ensure_share_permission(
        current_user,
        ShareAction.READ,
        share_id=share_id,
        share_user_id=owner_id,
    )

    if not getattr(current_user, "is_superuser", False) and not await _user_can_see_share(
        session,
        row=row,
        user_id=current_user.id,
        resource_owner_id=owner_id,
    ):
        # UUID privacy: forbidden share → 404.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")

    return ShareRead.model_validate(row, from_attributes=True)


@router.patch("/{share_id}", response_model=ShareRead)
async def update_share(
    share_id: UUID,
    payload: ShareUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ShareRead:
    """Update the permission level of an existing share."""
    row = await session.get(AuthzShare, share_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")

    owner_id = await _resolve_resource_owner(
        session,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
    )
    await _ensure_can_administer_share(user=current_user, owner_id=owner_id)
    # See create_share: owner_id is the *resource* owner so non-owners are
    # forced through ensure_share_permission's plugin enforce() path.
    await ensure_share_permission(
        current_user,
        ShareAction.UPDATE,
        share_id=share_id,
        share_user_id=owner_id,
    )

    # Validate permission_level (422 before DB CHECK).
    try:
        row.permission_level = SharePermissionLevel(payload.permission_level).value
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown permission_level {payload.permission_level!r}",
        ) from exc
    session.add(row)
    # Rollback + fixed 409 on constraint failure (same as create_share).
    try:
        await session.flush()
    except Exception as exc:
        await session.rollback()
        logger.warning("authz_share update rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Share could not be updated: it may conflict with an existing share.",
        ) from exc
    await session.refresh(row)

    await _invalidate_for_share(row.scope, row.target_id)

    await audit_decision(
        user_id=current_user.id,
        action="share:update",
        obj=f"{row.resource_type}:{row.resource_id}",
        result="allow",
        details={
            "share_id": str(row.id),
            "permission_level": row.permission_level,
        },
    )
    return ShareRead.model_validate(row, from_attributes=True)


@router.delete("/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_share(
    share_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> None:
    """Revoke an existing share."""
    row = await session.get(AuthzShare, share_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")

    owner_id = await _resolve_resource_owner(
        session,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
    )
    await _ensure_can_administer_share(user=current_user, owner_id=owner_id)
    # See create_share: owner_id is the *resource* owner so non-owners are
    # forced through ensure_share_permission's plugin enforce() path.
    await ensure_share_permission(
        current_user,
        ShareAction.DELETE,
        share_id=share_id,
        share_user_id=owner_id,
    )

    target_id = row.target_id
    resource_type = row.resource_type
    resource_id = row.resource_id
    scope = row.scope
    await session.delete(row)
    await session.flush()

    await _invalidate_for_share(scope, target_id)

    await audit_decision(
        user_id=current_user.id,
        action="share:delete",
        obj=f"{resource_type}:{resource_id}",
        result="allow",
        details={"share_id": str(share_id)},
    )


__all__ = ["router"]
