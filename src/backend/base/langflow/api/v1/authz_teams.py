"""CRUD API for authz_team and authz_team_member rows.

Teams group users for bulk role assignment and share targeting. The
authorization plugin compiles team memberships into its own representation
during policy sync.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas.authz_teams import (
    TeamCreate,
    TeamMemberCreate,
    TeamMemberRead,
    TeamRead,
    TeamUpdate,
)
from langflow.services.authorization.invalidation import (
    safe_invalidate_all,
    safe_invalidate_user,
)
from langflow.services.authorization.utils import audit_decision
from langflow.services.database.models.auth import AuthzTeam, AuthzTeamMember
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_authorization_service

router = APIRouter(prefix="/authz/teams", tags=["Authorization"])

# See ``authz_roles._LIST_MAX_LIMIT`` — same bound, applied to teams + members.
_LIST_MAX_LIMIT = 200
_LIST_DEFAULT_LIMIT = 100


def _require_superuser(user) -> None:
    if not getattr(user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser required to administer teams.",
        )


# --- teams ---------------------------------------------------------------- #


@router.get("", response_model=list[TeamRead])
@router.get("/", response_model=list[TeamRead])
async def list_teams(
    session: DbSession,
    current_user: CurrentActiveUser,  # noqa: ARG001 — any authenticated user can list
    search: Annotated[str | None, Query(description="Substring match on team_name or adom_name")] = None,
    is_active: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_LIST_MAX_LIMIT)] = _LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TeamRead]:
    """List teams. Open to any authenticated user (for the share dialog's team picker).

    Paginated via ``limit`` / ``offset`` so a single call cannot enumerate every
    team. Stable order is ``(team_name, id)`` so ``offset`` is deterministic.
    """
    stmt = select(AuthzTeam)
    if search:
        like = f"%{search}%"
        stmt = stmt.where((AuthzTeam.team_name.ilike(like)) | (AuthzTeam.adom_name.ilike(like)))
    if is_active is not None:
        stmt = stmt.where(AuthzTeam.is_active == is_active)
    stmt = stmt.order_by(AuthzTeam.team_name, AuthzTeam.id).offset(offset).limit(limit)
    rows = (await session.exec(stmt)).all()
    return [TeamRead.model_validate(row) for row in rows]


@router.get("/{team_id}", response_model=TeamRead)
async def read_team(
    team_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,  # noqa: ARG001
) -> TeamRead:
    team = await session.get(AuthzTeam, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return TeamRead.model_validate(team)


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> TeamRead:
    _require_superuser(current_user)
    team = AuthzTeam(
        team_name=payload.team_name,
        adom_name=payload.adom_name,
        description=payload.description,
        is_active=payload.is_active,
    )
    session.add(team)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Team with adom_name {payload.adom_name!r} already exists",
        ) from exc
    await session.refresh(team)
    await audit_decision(
        user_id=current_user.id,
        action="team:create",
        obj=f"team:{team.id}",
        result="allow",
        details={"team_name": team.team_name, "adom_name": team.adom_name},
    )
    logger.info("Created team %s (id=%s)", team.team_name, team.id)
    return TeamRead.model_validate(team)


@router.patch("/{team_id}", response_model=TeamRead)
async def update_team(
    team_id: UUID,
    payload: TeamUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> TeamRead:
    _require_superuser(current_user)
    team = await session.get(AuthzTeam, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    # Track whether the change affects fields a plugin may read during
    # policy sync (the team's domain slug or active state). description-only
    # / team_name-only edits are display metadata; adom_name and is_active
    # can influence which rules match.
    policy_relevant_changed = False
    changed_fields: list[str] = []
    if payload.team_name is not None and team.team_name != payload.team_name:
        team.team_name = payload.team_name
        changed_fields.append("team_name")
    if payload.adom_name is not None and team.adom_name != payload.adom_name:
        team.adom_name = payload.adom_name
        changed_fields.append("adom_name")
        policy_relevant_changed = True
    # description is nullable on the DB side, so use a presence check
    # (model_fields_set) instead of ``is not None`` — an explicit "description":
    # null in the body clears the field, while omitting it leaves the row alone.
    if "description" in payload.model_fields_set and team.description != payload.description:
        team.description = payload.description
        changed_fields.append("description")
    if payload.is_active is not None and team.is_active != payload.is_active:
        team.is_active = payload.is_active
        changed_fields.append("is_active")
        policy_relevant_changed = True
    team.updated_at = datetime.now(timezone.utc)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="adom_name conflict — another team already uses this slug",
        ) from exc
    await session.refresh(team)
    # Pure display edits (team_name, description) don't change policy. But
    # adom_name is the slug a plugin may use to compile rules against, and
    # is_active gates whether the team's memberships should grant access at
    # all — invalidate so the next enforce reflects the new state.
    if policy_relevant_changed:
        await safe_invalidate_all(get_authorization_service(), op="team:update")
    await audit_decision(
        user_id=current_user.id,
        action="team:update",
        obj=f"team:{team.id}",
        result="allow",
        details={"team_name": team.team_name, "fields_changed": sorted(changed_fields)},
    )
    logger.info("Updated team %s (id=%s)", team.team_name, team.id)
    return TeamRead.model_validate(team)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> None:
    _require_superuser(current_user)
    team = await session.get(AuthzTeam, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    team_name = team.team_name
    # Cascade on team_members handles cleanup; share rows targeting this team
    # are left in place (caller may want to migrate them before deleting).
    await session.delete(team)
    await session.commit()
    await safe_invalidate_all(get_authorization_service(), op="team:delete")
    await audit_decision(
        user_id=current_user.id,
        action="team:delete",
        obj=f"team:{team_id}",
        result="allow",
        details={"team_name": team_name},
    )
    logger.info("Deleted team id=%s", team_id)


# --- team members --------------------------------------------------------- #


@router.get("/{team_id}/members", response_model=list[TeamMemberRead])
async def list_members(
    team_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,  # noqa: ARG001
    limit: Annotated[int, Query(ge=1, le=_LIST_MAX_LIMIT)] = _LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TeamMemberRead]:
    """List members of a team. Any authenticated user (so the UI can render team rosters).

    Paginated via ``limit`` / ``offset`` so a single call cannot enumerate a
    large team's full roster. Stable order is ``(created_at, user_id)``.
    """
    team = await session.get(AuthzTeam, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    stmt = (
        select(AuthzTeamMember)
        .where(AuthzTeamMember.team_id == team_id)
        .order_by(AuthzTeamMember.created_at, AuthzTeamMember.user_id)
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.exec(stmt)).all()
    return [TeamMemberRead.model_validate(row) for row in rows]


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    team_id: UUID,
    payload: TeamMemberCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> TeamMemberRead:
    _require_superuser(current_user)
    team = await session.get(AuthzTeam, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    user = await session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_id not found")

    member = AuthzTeamMember(
        team_id=team_id,
        user_id=payload.user_id,
        source=payload.source,
    )
    session.add(member)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this team",
        ) from exc
    await session.refresh(member)
    await safe_invalidate_user(
        get_authorization_service(),
        payload.user_id,
        op="team_member:create",
    )
    await audit_decision(
        user_id=current_user.id,
        action="team_member:create",
        obj=f"team:{team_id}",
        result="allow",
        details={
            "team_name": team.team_name,
            "user_id": str(payload.user_id),
            "source": payload.source,
        },
    )
    logger.info("Added user=%s to team=%s", payload.user_id, team_id)
    return TeamMemberRead.model_validate(member)


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    team_id: UUID,
    user_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> None:
    _require_superuser(current_user)
    member = (
        await session.exec(
            select(AuthzTeamMember).where(
                AuthzTeamMember.team_id == team_id,
                AuthzTeamMember.user_id == user_id,
            )
        )
    ).first()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )
    await session.delete(member)
    await session.commit()
    await safe_invalidate_user(
        get_authorization_service(),
        user_id,
        op="team_member:delete",
    )
    await audit_decision(
        user_id=current_user.id,
        action="team_member:delete",
        obj=f"team:{team_id}",
        result="allow",
        details={"user_id": str(user_id)},
    )
    logger.info("Removed user=%s from team=%s", user_id, team_id)
