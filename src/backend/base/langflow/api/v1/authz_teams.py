"""Team administration API backed by one invariant-preserving mutation path."""

from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from lfx.utils.util_strings import escape_like_pattern
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas.authz_teams import (
    TeamCapabilities,
    TeamCreate,
    TeamMemberCreate,
    TeamMemberRead,
    TeamMemberRoleUpdate,
    TeamRead,
    TeamRoleLiteral,
    TeamUpdate,
)
from langflow.services.authorization.access_ceiling import external_access_allows
from langflow.services.authorization.collaboration import (
    CollaborationCapabilityError,
    discover_collaboration_capabilities,
)
from langflow.services.authorization.fetch import authorization_admission
from langflow.services.authorization.lifecycle import safe_identity_mutation_committed
from langflow.services.authorization.team_management import (
    MemberUpsert,
    TeamManagementError,
    TeamPatch,
    actor_can_administer_platform,
    team_actor_capabilities_many,
)
from langflow.services.authorization.team_management import (
    add_member as add_member_transaction,
)
from langflow.services.authorization.team_management import (
    change_member_role as change_member_role_transaction,
)
from langflow.services.authorization.team_management import (
    create_team as create_team_transaction,
)
from langflow.services.authorization.team_management import (
    delete_team as delete_team_transaction,
)
from langflow.services.authorization.team_management import (
    patch_team as patch_team_transaction,
)
from langflow.services.authorization.team_management import (
    remove_member as remove_member_transaction,
)
from langflow.services.authorization.utils import audit_decision
from langflow.services.database.lock_retry import run_with_lock_retry
from langflow.services.database.models.auth import AuthzTeam, AuthzTeamMember
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_authorization_service

router = APIRouter(prefix="/authz/teams", tags=["Authorization"])

_LIST_MAX_LIMIT = 200
_LIST_DEFAULT_LIMIT = 100
TeamView = Literal["directory", "member", "managed", "all"]


async def _require_superuser_dependency(current_user: CurrentActiveUser) -> None:
    """Reject non-platform administrators before validating create payloads.

    The historical helper name is retained because structural security tests
    inspect this dependency. The actual decision also applies the current
    external-credential ceiling through ``actor_can_administer_platform``.
    """
    if not actor_can_administer_platform(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform Admin required")


def _require_credential_action(action: str) -> None:
    if not external_access_allows(action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External credentials do not allow this action",
        )


def _raise_domain_error(exc: TeamManagementError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


async def _require_collaboration_ready() -> None:
    try:
        capabilities = await discover_collaboration_capabilities()
    except CollaborationCapabilityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTHORIZATION_NOT_READY", "message": "Authorization is not ready."},
        ) from exc
    if not capabilities.collaboration_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTHORIZATION_NOT_READY", "message": "Authorization is not ready."},
        )


async def _current_actor(session: DbSession, user_id: UUID) -> User:
    actor = await session.get(User, user_id, populate_existing=True)
    if actor is None or actor.is_active is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return actor


async def _team_visible(session: DbSession, *, team_id: UUID, user: User) -> bool:
    async with authorization_admission(session):
        return await get_authorization_service().enforce(user_id=user.id, domain="*", obj=f"team:{team_id}", act="read")


async def _serialize_team(session: DbSession, team: AuthzTeam, actor: User) -> TeamRead:
    return (await _serialize_teams(session, [team], actor))[0]


async def _serialize_teams(session: DbSession, teams: list[AuthzTeam], actor: User) -> list[TeamRead]:
    """Serialize a page with two batched roster reads instead of per-team queries."""
    if not teams:
        return []
    team_ids = [team.id for team in teams]
    members = list(
        (
            await session.exec(
                select(AuthzTeamMember)
                .where(col(AuthzTeamMember.team_id).in_(team_ids))
                .order_by(col(AuthzTeamMember.team_id), col(AuthzTeamMember.user_id))
            )
        ).all()
    )
    user_ids = tuple({member.user_id for member in members})
    active_ids: set[UUID] = set()
    if user_ids:
        active_ids = set(
            (
                await session.exec(
                    select(User.id).where(col(User.id).in_(user_ids), User.is_active == True)  # noqa: E712
                )
            ).all()
        )
    by_team: dict[UUID, list[AuthzTeamMember]] = {}
    for member in members:
        by_team.setdefault(member.team_id, []).append(member)

    capability_by_team = await team_actor_capabilities_many(session, actor=actor, team_ids=team_ids)
    serialized: list[TeamRead] = []
    for team in teams:
        roster = by_team.get(team.id, [])
        capabilities = capability_by_team[team.id]
        serialized.append(
            TeamRead(
                **team.model_dump(),
                member_count=len(roster),
                active_member_count=sum(member.user_id in active_ids for member in roster),
                active_admin_count=sum(member.user_id in active_ids and member.role == "admin" for member in roster),
                current_user_role=cast(TeamRoleLiteral | None, capabilities.current_user_role),
                capabilities=TeamCapabilities(
                    can_update=capabilities.can_update,
                    can_set_active=capabilities.can_set_active,
                    can_delete=capabilities.can_delete,
                    can_add_user_member=capabilities.can_add_user_member,
                    can_add_privileged_member=capabilities.can_add_privileged_member,
                    can_change_roles=capabilities.can_change_roles,
                    can_remove_user_member=capabilities.can_remove_user_member,
                ),
            )
        )
    return serialized


async def _serialize_member(session: DbSession, member: AuthzTeamMember) -> TeamMemberRead:
    user = await session.get(User, member.user_id)
    return TeamMemberRead(
        **member.model_dump(),
        display_name=user.username if user is not None else None,
        avatar=user.profile_image if user is not None else None,
    )


async def _serialize_members(session: DbSession, members: list[AuthzTeamMember]) -> list[TeamMemberRead]:
    if not members:
        return []
    users = (await session.exec(select(User).where(col(User.id).in_([member.user_id for member in members])))).all()
    by_id = {user.id: user for user in users}
    return [
        TeamMemberRead(
            **member.model_dump(),
            display_name=by_id[member.user_id].username if member.user_id in by_id else None,
            avatar=by_id[member.user_id].profile_image if member.user_id in by_id else None,
        )
        for member in members
    ]


@router.get("", response_model=list[TeamRead])
@router.get("/", response_model=list[TeamRead])
async def list_teams(
    session: DbSession,
    current_user: CurrentActiveUser,
    view: Annotated[TeamView, Query()] = "member",
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    is_active: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_LIST_MAX_LIMIT)] = _LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TeamRead]:
    """List a bounded caller-authorized team view."""
    async with authorization_admission(session) as admission:
        actor = await _current_actor(admission, current_user.id)
        statement = select(AuthzTeam)
        if view == "all":
            if not actor_can_administer_platform(actor):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform Admin required")
        elif view in {"member", "managed"}:
            statement = statement.join(
                AuthzTeamMember,
                col(AuthzTeamMember.team_id) == col(AuthzTeam.id),
            ).where(AuthzTeamMember.user_id == actor.id)
            if view == "managed":
                statement = statement.where(col(AuthzTeamMember.role).in_(("admin", "maintainer")))
        elif view == "directory":
            statement = statement.where(AuthzTeam.is_active == True)  # noqa: E712

        if search:
            normalized = search.strip()
            if normalized:
                like = f"%{escape_like_pattern(normalized)}%"
                statement = statement.where(
                    col(AuthzTeam.team_name).ilike(like, escape="\\")
                    | col(AuthzTeam.adom_name).ilike(like, escape="\\")
                )
        if is_active is not None:
            statement = statement.where(AuthzTeam.is_active == is_active)
        statement = statement.order_by(col(AuthzTeam.team_name), col(AuthzTeam.id))
        if view in {"member", "managed"}:
            # Membership narrows the requested view; the engine still decides
            # visibility before the caller's offset and limit are applied.
            teams: list[AuthzTeam] = []
            scanned = visible = 0
            while len(teams) < limit:
                candidates = list((await admission.exec(statement.offset(scanned).limit(_LIST_MAX_LIMIT))).all())
                if not candidates:
                    break
                decisions = await get_authorization_service().batch_enforce(
                    user_id=actor.id, domain="*", requests=tuple((f"team:{team.id}", "read") for team in candidates)
                )
                for team, allowed in zip(candidates, decisions, strict=True):
                    if allowed:
                        if visible >= offset:
                            teams.append(team)
                        visible += 1
                        if len(teams) == limit:
                            break
                scanned += len(candidates)
        else:
            teams = list((await admission.exec(statement.offset(offset).limit(limit))).all())
        return await _serialize_teams(admission, teams, actor)


@router.get("/{team_id}", response_model=TeamRead)
async def read_team(
    team_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> TeamRead:
    async with authorization_admission(session) as admission:
        actor = await _current_actor(admission, current_user.id)
        team = await admission.get(AuthzTeam, team_id)
        if team is None or not await _team_visible(admission, team_id=team_id, user=actor):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        return await _serialize_team(admission, team, actor)


@router.post(
    "",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_superuser_dependency)],
)
@router.post(
    "/",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_superuser_dependency)],
)
async def create_team(
    payload: TeamCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> TeamRead:
    actor_id = current_user.id
    actor = await _current_actor(session, actor_id)
    if not actor_can_administer_platform(actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform Admin required")
    _require_credential_action("create")
    await _require_collaboration_ready()

    async def operation(_attempt: int):
        return await create_team_transaction(
            session,
            actor=actor,
            team_name=payload.team_name,
            adom_name=payload.adom_name,
            description=payload.description,
            is_active=payload.is_active,
            members=tuple(MemberUpsert(member.user_id, member.role) for member in payload.members),
        )

    try:
        result = await run_with_lock_retry(operation, session=session, description="create team")
        await session.commit()
    except TeamManagementError as exc:
        await session.rollback()
        _raise_domain_error(exc)
    for event in result.events:
        await safe_identity_mutation_committed(get_authorization_service(), event)
    await session.refresh(result.team)
    actor = await _current_actor(session, actor_id)
    return await _serialize_team(session, result.team, actor)


@router.patch("/{team_id}", response_model=TeamRead)
async def update_team(
    team_id: UUID,
    payload: TeamUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> TeamRead:
    _require_credential_action("write")
    await _require_collaboration_ready()
    actor_id = current_user.id
    patch = TeamPatch(
        team_name=payload.team_name,
        adom_name=payload.adom_name,
        description=payload.description,
        description_supplied="description" in payload.model_fields_set,
        is_active=payload.is_active,
        member_upserts=tuple(MemberUpsert(member.user_id, member.role) for member in payload.member_upserts),
        remove_member_ids=tuple(payload.remove_member_ids),
    )

    async def operation(_attempt: int):
        actor = await _current_actor(session, actor_id)
        return await patch_team_transaction(session, actor=actor, team_id=team_id, patch=patch)

    try:
        result = await run_with_lock_retry(operation, session=session, description=f"update team {team_id}")
        await session.commit()
    except TeamManagementError as exc:
        await session.rollback()
        _raise_domain_error(exc)
    for event in result.events:
        await safe_identity_mutation_committed(get_authorization_service(), event)
    await session.refresh(result.team)
    actor = await _current_actor(session, actor_id)
    return await _serialize_team(session, result.team, actor)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> None:
    actor_id = current_user.id
    actor = await _current_actor(session, actor_id)
    if not actor_can_administer_platform(actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform Admin required")
    _require_credential_action("delete")
    await _require_collaboration_ready()

    async def operation(_attempt: int):
        return await delete_team_transaction(session, actor=actor, team_id=team_id)

    try:
        event = await run_with_lock_retry(operation, session=session, description=f"delete team {team_id}")
        await session.commit()
    except TeamManagementError as exc:
        await session.rollback()
        _raise_domain_error(exc)
    await safe_identity_mutation_committed(get_authorization_service(), event)


@router.get("/{team_id}/members", response_model=list[TeamMemberRead])
async def list_members(
    team_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    limit: Annotated[int, Query(ge=1, le=_LIST_MAX_LIMIT)] = _LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TeamMemberRead]:
    async with authorization_admission(session) as admission:
        actor = await _current_actor(admission, current_user.id)
        team = await admission.get(AuthzTeam, team_id)
        if team is None or not await _team_visible(admission, team_id=team_id, user=actor):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        statement = (
            select(AuthzTeamMember)
            .where(AuthzTeamMember.team_id == team_id)
            .order_by(col(AuthzTeamMember.created_at), col(AuthzTeamMember.user_id))
            .offset(offset)
            .limit(limit)
        )
        members = list((await admission.exec(statement)).all())
        return await _serialize_members(admission, members)


@router.post("/{team_id}/members", response_model=TeamMemberRead, status_code=status.HTTP_201_CREATED)
async def add_member(
    team_id: UUID,
    payload: TeamMemberCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> TeamMemberRead:
    _require_credential_action("create")
    await _require_collaboration_ready()
    actor_id = current_user.id

    async def operation(_attempt: int):
        actor = await _current_actor(session, actor_id)
        return await add_member_transaction(
            session,
            actor=actor,
            team_id=team_id,
            member=MemberUpsert(payload.user_id, payload.role),
        )

    try:
        result = await run_with_lock_retry(operation, session=session, description=f"add member to {team_id}")
        await session.commit()
    except TeamManagementError as exc:
        await session.rollback()
        _raise_domain_error(exc)
    for event in result.events:
        await safe_identity_mutation_committed(get_authorization_service(), event)
    await session.refresh(result.member)
    return await _serialize_member(session, result.member)


@router.patch("/{team_id}/members/{user_id}", response_model=TeamMemberRead)
async def change_member_role(
    team_id: UUID,
    user_id: UUID,
    payload: TeamMemberRoleUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> TeamMemberRead:
    _require_credential_action("write")
    await _require_collaboration_ready()
    actor_id = current_user.id

    async def operation(_attempt: int):
        actor = await _current_actor(session, actor_id)
        return await change_member_role_transaction(
            session,
            actor=actor,
            team_id=team_id,
            user_id=user_id,
            role=payload.role,
        )

    try:
        result = await run_with_lock_retry(operation, session=session, description=f"change member role in {team_id}")
        await session.commit()
    except TeamManagementError as exc:
        await session.rollback()
        _raise_domain_error(exc)
    for event in result.events:
        await safe_identity_mutation_committed(get_authorization_service(), event)
    await session.refresh(result.member)
    return await _serialize_member(session, result.member)


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    team_id: UUID,
    user_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> None:
    _require_credential_action("delete")
    await _require_collaboration_ready()
    actor_id = current_user.id

    async def operation(_attempt: int):
        actor = await _current_actor(session, actor_id)
        return await remove_member_transaction(session, actor=actor, team_id=team_id, user_id=user_id)

    try:
        events = await run_with_lock_retry(operation, session=session, description=f"remove member from {team_id}")
        await session.commit()
    except TeamManagementError as exc:
        await session.rollback()
        _raise_domain_error(exc)
    for event in events:
        await safe_identity_mutation_committed(get_authorization_service(), event)


__all__ = ["audit_decision", "router"]
