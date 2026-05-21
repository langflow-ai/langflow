"""CRUD API for ``authz_share`` rows.

This router is the OSS-side admin surface for resource-level shares. It does
not interpret share rows for enforcement — that is the Enterprise plugin's
job — but it writes the canonical rows so plugins have something to compile
into Casbin policy via ``PolicySync``.

Authorization model
-------------------

* Creating, listing, updating, or deleting a share on a resource is gated by
  ``share:{action}`` (via :func:`ensure_share_permission`) and falls through
  to the OSS pass-through (allow-all) unless an enterprise plugin is
  registered.
* The route handler also enforces an OSS-side floor: only the resource owner
  or a superuser may write shares for that resource. This prevents the OSS
  pass-through default from silently letting a viewer-role user hand out
  grants on someone else's resource.
* Non-owners listing shares only see rows whose ``target_id`` matches their
  own user id (so users can see what's been shared *with* them without
  seeing the full grant ledger).
"""

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


# Map resource type slug → (SQLModel, FK-to-user column attribute). Knowledge
# bases use ``KnowledgeBaseRecord`` (UUID primary key) so the share row's
# UUID-typed ``resource_id`` aligns with the Casbin object key
# (``knowledge_base:{kb_id}``) emitted by ``ensure_knowledge_base_permission``.
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


async def _user_can_see_share(
    session: DbSession,
    *,
    row: AuthzShare,
    user_id: UUID,
    resource_owner_id: UUID | None,
) -> bool:
    """Return True when ``user_id`` is permitted to see ``row`` in list/get.

    Visibility tiers (any one is sufficient):

    * resource owner — full visibility on shares of their own resource;
    * share creator — needs to manage their own grants;
    * user-scoped target — needs to know what's been shared with them;
    * team-scoped target — caller is a member of ``row.target_id``;
    * public scope — anyone in the system can see the row exists.
    """
    if user_id in {resource_owner_id, row.created_by}:
        return True
    scope = row.scope
    if scope == ShareScope.PUBLIC.value:
        return True
    if scope == ShareScope.USER.value and row.target_id == user_id:
        return True
    if scope == ShareScope.TEAM.value and row.target_id is not None:
        membership_stmt = select(AuthzTeamMember).where(
            AuthzTeamMember.team_id == row.target_id,
            AuthzTeamMember.user_id == user_id,
        )
        member = (await session.exec(membership_stmt)).first()
        return member is not None
    return False


async def _invalidate_for_share(scope: str, target_id: UUID | None) -> None:
    """Drop cached policy after a share write, scoped to the share's audience.

    The plugin-side ``invalidate_user(uuid)`` API only knows about user ids,
    so ``target_id`` is *only* a valid argument when ``scope == "user"``.
    For team / private / public shares (and for unknown scopes), fall back
    to ``invalidate_all`` — otherwise we'd hand the enforcer a team uuid as
    if it were a user uuid and the actual team members' cache would stay
    stale.
    """
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
    """OSS floor: only resource owner or superuser may write shares.

    When an enterprise plugin is actively enforcing (cross-user fetch
    supported AND ``LANGFLOW_AUTHZ_ENABLED=true``) this floor is skipped so
    a workspace/admin role with ``share:create`` can administer shares for
    resources it doesn't own; ``ensure_share_permission`` is the
    authoritative check in that mode. Under the OSS pass-through (allow-all
    enforce) the floor stays in place so a viewer cannot mint share rows for
    someone else's resource.
    """
    if getattr(user, "is_superuser", False):
        return
    if owner_id is not None and owner_id == user.id:
        return
    authz = get_authorization_service()
    if await authz.supports_cross_user_fetch() and await authz.is_enabled():
        # Enterprise plugin is active — let ``ensure_share_permission``
        # decide (its decision will fire downstream of this helper).
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
    """Create an ``authz_share`` row granting access to a resource.

    The caller must be the resource owner or a superuser. The plugin-level
    ``share:create`` guard fires after the OSS owner check, so an enterprise
    plugin can additionally deny owners with insufficient role.
    """
    owner_id = await _resolve_resource_owner(
        session,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
    )
    if owner_id is None:
        # The resource simply does not exist — UUID privacy: 404.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    await _ensure_can_administer_share(user=current_user, owner_id=owner_id)
    await ensure_share_permission(
        current_user,
        ShareAction.CREATE,
        share_user_id=current_user.id,
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
        # Log the raw exception server-side; the client gets a fixed string
        # so we don't leak table/column/constraint names through the 409
        # body (security rule: error messages don't disclose schema).
        await session.rollback()
        logger.warning("authz_share insert rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Share could not be created: it may already exist or conflict with an existing share.",
        ) from exc
    await session.refresh(row)

    # Tell the enforcer (if any) to drop its cached policy. Use the share's
    # scope to pick the right invalidation — a team's target_id is a team
    # uuid, not a user uuid, so ``invalidate_user`` would not reach members.
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
    """List share rows.

    Resource owners and superusers see every matching row. Non-owners only
    see rows whose ``target_id`` is their own user id, rows scoped to a team
    they belong to, public rows, or rows on resources they own.

    Always paginated — ``limit`` is capped at 200 to bound DB load. The
    previous unbounded implementation issued an N+1 ``select(AuthzTeamMember)``
    per row; this version pre-fetches the caller's team memberships once and
    uses an in-memory set lookup.
    """
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
        # Validate scope literal against the enum so unknown values 422 early.
        try:
            scope_value = ShareScope(scope).value
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Unknown scope {scope!r}") from exc
        stmt = stmt.where(AuthzShare.scope == scope_value)

    # Stable ordering + bounded fetch. ``created_at`` is monotonically
    # increasing for a given operator so this is effectively cursor-like;
    # callers wanting strict cursor pagination can layer ``id`` ties.
    stmt = stmt.order_by(AuthzShare.created_at.desc(), AuthzShare.id).offset(offset).limit(limit)

    rows = list(await session.exec(stmt))

    is_superuser = getattr(current_user, "is_superuser", False)
    if is_superuser:
        return [ShareRead.model_validate(row, from_attributes=True) for row in rows]

    # Pre-fetch the caller's team memberships once — the previous per-row
    # ``select(AuthzTeamMember)`` was an N+1 that scaled with the page size.
    team_membership_stmt = select(AuthzTeamMember.team_id).where(AuthzTeamMember.user_id == current_user.id)
    caller_team_ids: set[UUID] = set(await session.exec(team_membership_stmt))

    # Non-superuser visibility: owner / creator / direct user target / team
    # member / public. See ``_user_can_see_share`` for the full rule set.
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
    """In-memory variant of ``_user_can_see_share`` for the batch list path.

    Same rules as ``_user_can_see_share`` but team membership is checked via
    the pre-fetched ``caller_team_ids`` set so the list loop is O(N) instead
    of issuing one ``select(AuthzTeamMember)`` per row.
    """
    if user_id in {resource_owner_id, row.created_by}:
        return True
    scope = row.scope
    if scope == ShareScope.PUBLIC.value:
        return True
    if scope == ShareScope.USER.value and row.target_id == user_id:
        return True
    if scope == ShareScope.TEAM.value and row.target_id is not None:
        return row.target_id in caller_team_ids
    return False


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

    await ensure_share_permission(
        current_user,
        ShareAction.READ,
        share_id=share_id,
        share_user_id=row.created_by,
    )

    if not getattr(current_user, "is_superuser", False):
        owner_id = await _resolve_resource_owner(
            session,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
        )
        if not await _user_can_see_share(
            session,
            row=row,
            user_id=current_user.id,
            resource_owner_id=owner_id,
        ):
            # UUID privacy — caller is not allowed to know this share exists.
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
    await ensure_share_permission(
        current_user,
        ShareAction.UPDATE,
        share_id=share_id,
        share_user_id=row.created_by,
    )

    # Validate against the enum to keep the DB CHECK constraint happy and
    # surface unknown values as 422 instead of a constraint error.
    try:
        row.permission_level = SharePermissionLevel(payload.permission_level).value
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown permission_level {payload.permission_level!r}",
        ) from exc
    session.add(row)
    # Match the create_share error contract: rollback + fixed-string 409 +
    # server-side log so a constraint violation on update doesn't return a
    # raw SQLAlchemy stacktrace to the client.
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
    await ensure_share_permission(
        current_user,
        ShareAction.DELETE,
        share_id=share_id,
        share_user_id=row.created_by,
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
