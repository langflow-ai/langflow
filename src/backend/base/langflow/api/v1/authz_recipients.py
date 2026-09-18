"""Bounded recipient lookup authorized for one intended operation."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from lfx.utils.util_strings import escape_like_pattern
from sqlalchemy import exists, func, or_
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSessionReadOnly
from langflow.api.v1.schemas.authz_recipients import (
    AuthorizationRecipientPage,
    AuthorizationRecipientRead,
)
from langflow.services.authorization import ShareAction, ensure_resource_share_administration
from langflow.services.authorization.collaboration import (
    CollaborationCapabilityError,
    discover_collaboration_capabilities,
)
from langflow.services.authorization.fetch import authorization_admission, deny_to_404
from langflow.services.authorization.repository import load_active_user
from langflow.services.authorization.share_management import (
    ShareManagementError,
    resolve_resource_for_share,
)
from langflow.services.authorization.team_management import (
    actor_can_administer_platform,
    team_actor_capabilities,
)
from langflow.services.database.models.auth import AuthzTeam, AuthzTeamMember
from langflow.services.database.models.user.model import User

router = APIRouter(prefix="/authz/recipients", tags=["Authorization"])

RecipientPurpose = Literal["share", "team_membership"]
RecipientKind = Literal["user", "team"]
_MIN_QUERY_LENGTH = 2


def _not_ready(exc: Exception | None = None) -> HTTPException:  # noqa: ARG001
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "AUTHORIZATION_NOT_READY", "message": "Authorization is not ready."},
    )


async def _require_ready() -> None:
    try:
        capabilities = await discover_collaboration_capabilities()
    except CollaborationCapabilityError as exc:
        raise _not_ready(exc) from exc
    if not capabilities.collaboration_ready:
        raise _not_ready()


async def _authorize_share_search(
    *,
    current_user: User,
    session: DbSessionReadOnly,
    resource_type: str | None,
    resource_id: UUID | None,
) -> None:
    if resource_type not in {"flow", "project"} or resource_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "RECIPIENT_RESOURCE_REQUIRED",
                "message": "A flow or project resource is required for share recipient search.",
            },
        )
    try:
        resource = await resolve_resource_for_share(
            session,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    except ShareManagementError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found") from exc
    try:
        await ensure_resource_share_administration(
            current_user,
            ShareAction.CREATE,
            resource_type=resource.resource_type,
            resource_id=resource.resource_id,
            resource_owner_id=resource.owner_id,
            project_id=resource.project_id,
            workspace_id=resource.workspace_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, detail="Resource not found") from exc


async def _authorize_team_search(
    *,
    current_user: User,
    session: DbSessionReadOnly,
    team_id: UUID | None,
) -> None:
    if team_id is None:
        if not actor_can_administer_platform(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform Admin required")
        return
    team = await session.get(AuthzTeam, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    membership = (
        await session.exec(
            select(AuthzTeamMember.id).where(
                AuthzTeamMember.team_id == team_id,
                AuthzTeamMember.user_id == current_user.id,
            )
        )
    ).first()
    if not actor_can_administer_platform(current_user) and membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    capabilities = await team_actor_capabilities(session, actor=current_user, team_id=team_id)
    if not capabilities.can_add_user_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "TEAM_OPERATION_FORBIDDEN", "message": "You cannot add members to this team."},
        )


@router.get("", response_model=AuthorizationRecipientPage)
async def search_authorization_recipients(
    current_user: CurrentActiveUser,
    session: DbSessionReadOnly,
    purpose: Annotated[RecipientPurpose, Query()],
    kind: Annotated[RecipientKind, Query()],
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    resource_type: Annotated[str | None, Query()] = None,
    resource_id: Annotated[UUID | None, Query()] = None,
    team_id: Annotated[UUID | None, Query()] = None,
) -> AuthorizationRecipientPage:
    """Search active users or valid teams without exposing full profiles."""
    async with authorization_admission(session) as admission:
        normalized = q.strip()
        if len(normalized) < _MIN_QUERY_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "RECIPIENT_QUERY_TOO_SHORT",
                    "message": "Search text must contain at least 2 characters.",
                },
            )
        actor = await load_active_user(admission, current_user.id)
        if actor is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        await _require_ready()
        if purpose == "share":
            await _authorize_share_search(
                current_user=actor,
                session=admission,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        else:
            if kind != "user":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail={"code": "RECIPIENT_KIND_INVALID", "message": "Team membership search supports users only."},
                )
            await _authorize_team_search(current_user=actor, session=admission, team_id=team_id)

        pattern = f"%{escape_like_pattern(normalized.lower())}%"
        if kind == "user":
            user_statement = select(User).where(
                User.is_active == True,  # noqa: E712
                func.lower(User.username).like(pattern, escape="\\"),
            )
            if purpose == "team_membership" and team_id is not None:
                user_statement = user_statement.where(
                    ~exists(
                        select(AuthzTeamMember.id).where(
                            AuthzTeamMember.team_id == team_id,
                            AuthzTeamMember.user_id == User.id,
                        )
                    )
                )
            user_statement = (
                user_statement.order_by(func.lower(User.username), col(User.id)).offset(offset).limit(limit + 1)
            )
            user_rows = list((await admission.exec(user_statement)).all())
            items = [
                AuthorizationRecipientRead(
                    id=user.id,
                    kind="user",
                    display_name=user.username,
                    avatar=user.profile_image,
                )
                for user in user_rows[:limit]
            ]
            has_more = len(user_rows) > limit
        else:
            active_admin = exists(
                select(AuthzTeamMember.id)
                .join(User, col(User.id) == col(AuthzTeamMember.user_id))
                .where(
                    AuthzTeamMember.team_id == AuthzTeam.id,
                    AuthzTeamMember.role == "admin",
                    User.is_active == True,  # noqa: E712
                )
            )
            team_statement = (
                select(AuthzTeam)
                .where(
                    AuthzTeam.is_active == True,  # noqa: E712
                    active_admin,
                    or_(
                        func.lower(AuthzTeam.team_name).like(pattern, escape="\\"),
                        func.lower(AuthzTeam.adom_name).like(pattern, escape="\\"),
                    ),
                )
                .order_by(func.lower(AuthzTeam.team_name), col(AuthzTeam.id))
                .offset(offset)
                .limit(limit + 1)
            )
            team_rows = list((await admission.exec(team_statement)).all())
            items = [
                AuthorizationRecipientRead(id=team.id, kind="team", display_name=team.team_name)
                for team in team_rows[:limit]
            ]
            has_more = len(team_rows) > limit
        return AuthorizationRecipientPage(
            items=items,
            has_more=has_more,
            next_offset=offset + limit if has_more else None,
        )


__all__ = ["router"]
