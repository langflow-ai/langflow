"""CRUD API for authz_team and authz_team_member rows.

Teams group users for bulk role assignment and share targeting. The plugin
compiles team memberships to its own representation (e.g. enterprise Casbin
emits ``g, user:{id}, team:{id}, *`` rules during share PolicySync).
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
from langflow.services.database.models.auth import AuthzTeam, AuthzTeamMember
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_authorization_service

router = APIRouter(prefix="/authz/teams", tags=["Authorization"])


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
) -> list[TeamRead]:
    """List teams. Open to any authenticated user (for the share dialog's team picker)."""
    stmt = select(AuthzTeam)
    if search:
        like = f"%{search}%"
        stmt = stmt.where((AuthzTeam.team_name.ilike(like)) | (AuthzTeam.adom_name.ilike(like)))
    if is_active is not None:
        stmt = stmt.where(AuthzTeam.is_active == is_active)
    rows = (await session.exec(stmt.order_by(AuthzTeam.team_name))).all()
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

    if payload.team_name is not None:
        team.team_name = payload.team_name
    if payload.adom_name is not None:
        team.adom_name = payload.adom_name
    if payload.description is not None:
        team.description = payload.description
    if payload.is_active is not None:
        team.is_active = payload.is_active
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
    # Team metadata change doesn't require policy reload — only memberships do.
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
    # Cascade on team_members handles cleanup; share rows targeting this team
    # are left in place (caller may want to migrate them before deleting).
    await session.delete(team)
    await session.commit()
    await get_authorization_service().invalidate_all()
    logger.info("Deleted team id=%s", team_id)


# --- team members --------------------------------------------------------- #


@router.get("/{team_id}/members", response_model=list[TeamMemberRead])
async def list_members(
    team_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,  # noqa: ARG001
) -> list[TeamMemberRead]:
    """List members of a team. Any authenticated user (so the UI can render team rosters)."""
    team = await session.get(AuthzTeam, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    rows = (
        await session.exec(
            select(AuthzTeamMember)
            .where(AuthzTeamMember.team_id == team_id)
            .order_by(
                AuthzTeamMember.created_at,
            )
        )
    ).all()
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
    await get_authorization_service().invalidate_user(payload.user_id)
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
    await get_authorization_service().invalidate_user(user_id)
    logger.info("Removed user=%s from team=%s", user_id, team_id)
