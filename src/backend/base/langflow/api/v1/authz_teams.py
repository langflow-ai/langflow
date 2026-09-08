"""CRUD API for authz_team and authz_team_member rows.

Teams group users for bulk role assignment and share targeting. The
authorization plugin compiles team memberships into its own representation
during policy sync.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from lfx.log.logger import logger
from lfx.services.authorization import AuthorizationMutation, AuthorizationMutationKind, AuthorizationMutationRejected
from lfx.utils.util_strings import escape_like_pattern
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
from langflow.services.authorization.admin import (
    ADMINISTRATION_REQUIRED_REASON,
    administration_audit_details,
    administration_denied,
    is_administrator,
)
from langflow.services.authorization.audit import AUDIT_EVENT_ACCESS, AUDIT_EVENT_MUTATION
from langflow.services.authorization.lifecycle import (
    acquire_identity_mutation_lock,
    safe_identity_mutation_committed,
    stage_identity_mutation,
    validate_identity_mutation,
)
from langflow.services.authorization.team_member_grants import (
    TeamMemberGrantNotFoundError,
    ensure_team_member_grant,
    get_effective_team_member,
    get_team_member_grant,
    remove_team_member_grant,
)
from langflow.services.authorization.utils import audit_decision
from langflow.services.database.models.auth import AuthzTeam, AuthzTeamMember
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_authorization_service

router = APIRouter(prefix="/authz/teams", tags=["Authorization"], include_in_schema=False)

# See ``authz_roles._LIST_MAX_LIMIT`` — same bound, applied to teams + members.
_LIST_MAX_LIMIT = 200
_LIST_DEFAULT_LIMIT = 100
_EXTERNALLY_MANAGED_DETAIL = "Externally managed memberships cannot be removed through the manual membership API"
OperationId = Annotated[str | None, Header(alias="X-Langflow-Operation-ID", max_length=128)]
_LEGACY_SUPERUSER_DENIAL = "Superuser required to administer teams."


def _externally_managed_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=_EXTERNALLY_MANAGED_DETAIL,
        headers={"X-Langflow-Error-Code": "externally_managed"},
    )


async def _audit_deny(
    *,
    user_id: UUID,
    action: str,
    obj: str,
    status_code: int,
    reason: str,
    operation_id: str | None = None,
    source: str = "manual",
) -> None:
    await audit_decision(
        user_id=user_id,
        action=action,
        obj=obj,
        result="deny",
        details=administration_audit_details(
            {"event": AUDIT_EVENT_ACCESS, "status_code": status_code, "reason": reason},
            operation_id=operation_id,
            source=source,
        ),
    )


async def _require_team_administrator(user, *, action: str, obj: str, operation_id: str | None = None) -> None:
    """Allow superusers or a plugin-delegated ``team:manage`` administrator."""
    if await is_administrator(user, resource="team", authorization_service=get_authorization_service()):
        return
    await _audit_deny(
        user_id=user.id,
        action=action,
        obj=obj,
        status_code=status.HTTP_403_FORBIDDEN,
        reason=ADMINISTRATION_REQUIRED_REASON,
        operation_id=operation_id,
    )
    raise administration_denied(_LEGACY_SUPERUSER_DENIAL, resource="team")


async def _require_team_administrator_dependency(
    request: Request,
    current_user: CurrentActiveUser,
    operation_id: OperationId = None,
) -> None:
    """Run the team-administrator gate as a route dependency, i.e. before body validation.

    FastAPI solves a route's ``dependencies`` before validating that route's own
    body, so an unauthorised caller is refused whatever they post. Gated only in
    the endpoint body, they first receive the same 422 field names and enum
    values an administrator would, which lets them map the request contract of a
    route they cannot invoke.

    The in-body call is kept as well: it is the gate for anything that reaches
    the endpoint function without FastAPI resolving dependencies.
    """
    team_id = request.path_params.get("team_id", "*")
    is_member_route = "/members" in request.url.path
    action = (
        "team_member:create"
        if is_member_route and request.method == "POST"
        else "team_member:delete"
        if is_member_route and request.method == "DELETE"
        else {"POST": "team:create", "PATCH": "team:update", "DELETE": "team:delete"}.get(
            request.method,
            "team:access",
        )
    )
    await _require_team_administrator(current_user, action=action, obj=f"team:{team_id}", operation_id=operation_id)


TEAM_ADMINISTRATOR_ONLY = [Depends(_require_team_administrator_dependency)]


# --- teams ---------------------------------------------------------------- #


@router.get("", response_model=list[TeamRead])
@router.get("/", response_model=list[TeamRead])
async def list_teams(
    session: DbSession,
    current_user: CurrentActiveUser,  # noqa: ARG001 — any authenticated user can list
    search: Annotated[str | None, Query(description="Substring match on team_name or adom_name")] = None,
    adom_name: Annotated[str | None, Query(description="Exact match on adom_name")] = None,
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
        like = f"%{escape_like_pattern(search)}%"
        stmt = stmt.where(
            (AuthzTeam.team_name.ilike(like, escape="\\")) | (AuthzTeam.adom_name.ilike(like, escape="\\"))
        )
    if adom_name is not None:
        stmt = stmt.where(AuthzTeam.adom_name == adom_name)
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


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED, dependencies=TEAM_ADMINISTRATOR_ONLY)
@router.post("/", response_model=TeamRead, status_code=status.HTTP_201_CREATED, dependencies=TEAM_ADMINISTRATOR_ONLY)
async def create_team(
    payload: TeamCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
    response: Response,
    operation_id: OperationId = None,
) -> TeamRead:
    await _require_team_administrator(current_user, action="team:create", obj="team:*", operation_id=operation_id)
    authorization_service = get_authorization_service()
    await acquire_identity_mutation_lock(
        authorization_service,
        session,
        kind=AuthorizationMutationKind.TEAM_CREATED,
    )
    team = AuthzTeam(
        team_name=payload.team_name,
        adom_name=payload.adom_name,
        description=payload.description,
        is_active=payload.is_active,
    )
    session.add(team)
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.TEAM_CREATED,
        entity_id=team.id,
        actor_user_id=current_user.id,
        team_id=team.id,
        policy_relevant_fields=("adom_name", "is_active"),
    )
    try:
        await session.flush()
        await stage_identity_mutation(authorization_service, session, mutation)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        await _audit_deny(
            user_id=current_user.id,
            action="team:create",
            obj="team:*",
            status_code=status.HTTP_409_CONFLICT,
            reason="team_slug_conflict",
            operation_id=operation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Team with adom_name {payload.adom_name!r} already exists",
        ) from exc
    await safe_identity_mutation_committed(authorization_service, mutation)
    await session.refresh(team)
    await audit_decision(
        user_id=current_user.id,
        action="team:create",
        obj=f"team:{team.id}",
        result="allow",
        details=administration_audit_details(
            {"event": AUDIT_EVENT_MUTATION, "team_name": team.team_name, "adom_name": team.adom_name},
            operation_id=operation_id,
        ),
    )
    response.headers["Location"] = f"/api/v1/authz/teams/{team.id}"
    logger.info("Created team %s (id=%s)", team.team_name, team.id)
    return TeamRead.model_validate(team)


@router.patch("/{team_id}", response_model=TeamRead, dependencies=TEAM_ADMINISTRATOR_ONLY)
async def update_team(
    team_id: UUID,
    payload: TeamUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
    operation_id: OperationId = None,
) -> TeamRead:
    await _require_team_administrator(
        current_user,
        action="team:update",
        obj=f"team:{team_id}",
        operation_id=operation_id,
    )
    authorization_service = get_authorization_service()
    await acquire_identity_mutation_lock(
        authorization_service,
        session,
        kind=AuthorizationMutationKind.TEAM_UPDATED,
        entity_id=team_id,
    )
    team = await session.get(AuthzTeam, team_id)
    if team is None:
        await _audit_deny(
            user_id=current_user.id,
            action="team:update",
            obj=f"team:{team_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            reason="team_not_found",
            operation_id=operation_id,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    changed_fields: list[str] = []
    previous_adom_name = team.adom_name
    if payload.team_name is not None and team.team_name != payload.team_name:
        team.team_name = payload.team_name
        changed_fields.append("team_name")
    if payload.adom_name is not None and team.adom_name != payload.adom_name:
        team.adom_name = payload.adom_name
        changed_fields.append("adom_name")
    # description is nullable on the DB side, so use a presence check
    # (model_fields_set) instead of ``is not None`` — an explicit "description":
    # null in the body clears the field, while omitting it leaves the row alone.
    if "description" in payload.model_fields_set and team.description != payload.description:
        team.description = payload.description
        changed_fields.append("description")
    if payload.is_active is not None and team.is_active != payload.is_active:
        team.is_active = payload.is_active
        changed_fields.append("is_active")
    team.updated_at = datetime.now(timezone.utc)
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.TEAM_UPDATED,
        entity_id=team.id,
        actor_user_id=current_user.id,
        team_id=team.id,
        policy_relevant_fields=tuple(sorted(set(changed_fields) & {"adom_name", "is_active"})),
        previous_identifier=previous_adom_name if team.adom_name != previous_adom_name else None,
    )
    try:
        await session.flush()
        await stage_identity_mutation(authorization_service, session, mutation)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        await _audit_deny(
            user_id=current_user.id,
            action="team:update",
            obj=f"team:{team_id}",
            status_code=status.HTTP_409_CONFLICT,
            reason="team_slug_conflict",
            operation_id=operation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="adom_name conflict — another team already uses this slug",
        ) from exc
    await safe_identity_mutation_committed(authorization_service, mutation)
    await session.refresh(team)
    await audit_decision(
        user_id=current_user.id,
        action="team:update",
        obj=f"team:{team.id}",
        result="allow",
        details=administration_audit_details(
            {"event": AUDIT_EVENT_MUTATION, "team_name": team.team_name, "fields_changed": sorted(changed_fields)},
            operation_id=operation_id,
        ),
    )
    logger.info("Updated team %s (id=%s)", team.team_name, team.id)
    return TeamRead.model_validate(team)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=TEAM_ADMINISTRATOR_ONLY)
async def delete_team(
    team_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    operation_id: OperationId = None,
) -> None:
    await _require_team_administrator(
        current_user,
        action="team:delete",
        obj=f"team:{team_id}",
        operation_id=operation_id,
    )
    authorization_service = get_authorization_service()
    await acquire_identity_mutation_lock(
        authorization_service,
        session,
        kind=AuthorizationMutationKind.TEAM_DELETED,
        entity_id=team_id,
    )
    team = await session.get(AuthzTeam, team_id)
    if team is None:
        await _audit_deny(
            user_id=current_user.id,
            action="team:delete",
            obj=f"team:{team_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            reason="team_not_found",
            operation_id=operation_id,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    team_name = team.team_name
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.TEAM_DELETED,
        entity_id=team_id,
        actor_user_id=current_user.id,
        team_id=team_id,
        policy_relevant_fields=("adom_name", "is_active"),
        previous_identifier=team.adom_name,
    )
    # Cascade on team_members handles cleanup; share rows targeting this team
    # are left in place (caller may want to migrate them before deleting).
    await session.delete(team)
    await session.flush()
    await stage_identity_mutation(authorization_service, session, mutation)
    await session.commit()
    await safe_identity_mutation_committed(authorization_service, mutation)
    await audit_decision(
        user_id=current_user.id,
        action="team:delete",
        obj=f"team:{team_id}",
        result="allow",
        details=administration_audit_details(
            {"event": AUDIT_EVENT_MUTATION, "team_name": team_name},
            operation_id=operation_id,
        ),
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
    dependencies=TEAM_ADMINISTRATOR_ONLY,
)
async def add_member(
    team_id: UUID,
    payload: TeamMemberCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
    response: Response,
    operation_id: OperationId = None,
) -> TeamMemberRead:
    await _require_team_administrator(
        current_user,
        action="team_member:create",
        obj=f"team:{team_id}",
        operation_id=operation_id,
    )
    authorization_service = get_authorization_service()
    await acquire_identity_mutation_lock(
        authorization_service,
        session,
        kind=AuthorizationMutationKind.TEAM_MEMBER_ADDED,
        affected_user_ids=(payload.user_id,),
    )
    team = await session.get(AuthzTeam, team_id)
    if team is None:
        await _audit_deny(
            user_id=current_user.id,
            action="team_member:create",
            obj=f"team:{team_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            reason="team_not_found",
            operation_id=operation_id,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    user = await session.get(User, payload.user_id)
    if user is None:
        await _audit_deny(
            user_id=current_user.id,
            action="team_member:create",
            obj=f"team:{team_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            reason="user_not_found",
            operation_id=operation_id,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_id not found")

    member = await get_effective_team_member(session, team_id=team_id, user_id=payload.user_id)
    member_is_new = member is None
    if member is not None:
        existing_manual_grant = await get_team_member_grant(
            session,
            membership_id=member.id,
            source_kind="manual",
        )
        if existing_manual_grant is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a manual member of this team",
            )
    if member is None:
        member = AuthzTeamMember(
            team_id=team_id,
            user_id=payload.user_id,
            source=payload.source,
        )
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.TEAM_MEMBER_ADDED,
        entity_id=member.id,
        actor_user_id=current_user.id,
        affected_user_ids=(payload.user_id,),
        team_id=team_id,
        policy_relevant_fields=("team_id", "user_id", "source"),
    )
    try:
        if member_is_new:
            await validate_identity_mutation(authorization_service, session, mutation)
        change = await ensure_team_member_grant(
            session,
            team_id=team_id,
            user_id=payload.user_id,
            source_kind="manual",
            administrative_actor=current_user.id,
            membership=member,
            membership_is_new=member_is_new,
        )
        member = change.membership
        if member_is_new:
            await stage_identity_mutation(authorization_service, session, mutation)
        await session.commit()
    except AuthorizationMutationRejected as exc:
        await _audit_deny(
            user_id=current_user.id,
            action="team_member:create",
            obj=f"team:{team_id}",
            status_code=status.HTTP_409_CONFLICT,
            reason="access_ceiling",
            operation_id=operation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.public_detail,
            headers={"X-Langflow-Error-Code": "access_ceiling"},
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        await _audit_deny(
            user_id=current_user.id,
            action="team_member:create",
            obj=f"team:{team_id}",
            status_code=status.HTTP_409_CONFLICT,
            reason="membership_already_exists",
            operation_id=operation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this team",
        ) from exc
    if member_is_new:
        await safe_identity_mutation_committed(authorization_service, mutation)
    await session.refresh(member)
    await audit_decision(
        user_id=current_user.id,
        action="team_member:create",
        obj=f"team:{team_id}",
        result="allow",
        details=administration_audit_details(
            {"event": AUDIT_EVENT_MUTATION, "team_name": team.team_name, "user_id": str(payload.user_id)},
            operation_id=operation_id,
        ),
    )
    response.headers["Location"] = f"/api/v1/authz/teams/{team_id}/members/{payload.user_id}"
    logger.info("Added user=%s to team=%s", payload.user_id, team_id)
    return TeamMemberRead.model_validate(member)


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=TEAM_ADMINISTRATOR_ONLY,
)
async def remove_member(
    team_id: UUID,
    user_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    operation_id: OperationId = None,
) -> None:
    await _require_team_administrator(
        current_user,
        action="team_member:delete",
        obj=f"team:{team_id}",
        operation_id=operation_id,
    )
    authorization_service = get_authorization_service()
    await acquire_identity_mutation_lock(
        authorization_service,
        session,
        kind=AuthorizationMutationKind.TEAM_MEMBER_REMOVED,
        affected_user_ids=(user_id,),
    )
    member = await get_effective_team_member(session, team_id=team_id, user_id=user_id)
    if member is None:
        await _audit_deny(
            user_id=current_user.id,
            action="team_member:delete",
            obj=f"team:{team_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            reason="membership_not_found",
            operation_id=operation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )
    if member.source != "manual":
        await _audit_deny(
            user_id=current_user.id,
            action="team_member:delete",
            obj=f"team:{team_id}",
            status_code=status.HTTP_409_CONFLICT,
            reason="externally_managed",
            operation_id=operation_id,
            source=member.source,
        )
        raise _externally_managed_conflict()
    manual_grant = await get_team_member_grant(
        session,
        membership_id=member.id,
        source_kind="manual",
    )
    if manual_grant is None:
        raise _externally_managed_conflict()
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.TEAM_MEMBER_REMOVED,
        entity_id=member.id,
        actor_user_id=current_user.id,
        affected_user_ids=(user_id,),
        team_id=team_id,
        policy_relevant_fields=("team_id", "user_id", "source"),
    )
    try:
        await validate_identity_mutation(authorization_service, session, mutation)
    except AuthorizationMutationRejected as exc:
        await _audit_deny(
            user_id=current_user.id,
            action="team_member:delete",
            obj=f"team:{team_id}",
            status_code=status.HTTP_409_CONFLICT,
            reason="access_ceiling",
            operation_id=operation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.public_detail,
            headers={"X-Langflow-Error-Code": "access_ceiling"},
        ) from exc
    try:
        await remove_team_member_grant(
            session,
            team_id=team_id,
            user_id=user_id,
            source_kind="manual",
            membership=member,
            grant=manual_grant,
        )
    except TeamMemberGrantNotFoundError as exc:
        raise _externally_managed_conflict() from exc
    await stage_identity_mutation(authorization_service, session, mutation)
    await session.commit()
    await safe_identity_mutation_committed(authorization_service, mutation)
    await audit_decision(
        user_id=current_user.id,
        action="team_member:delete",
        obj=f"team:{team_id}",
        result="allow",
        details=administration_audit_details(
            {"event": AUDIT_EVENT_MUTATION, "user_id": str(user_id)},
            operation_id=operation_id,
        ),
    )
    logger.info("Removed user=%s from team=%s", user_id, team_id)
