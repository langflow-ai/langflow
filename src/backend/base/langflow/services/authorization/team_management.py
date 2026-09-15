"""Single transactional mutation path for teams and memberships."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.services.authorization import AuthorizationMutation, AuthorizationMutationKind, ShareRuleSnapshot
from lfx.services.authorization.context import authorization_session
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from langflow.services.authorization.access_ceiling import (
    EXTERNAL_ACCESS_ADMIN,
    external_access_allows,
    get_current_external_access_context,
)
from langflow.services.authorization.admin import administration_audit_details, is_administrator
from langflow.services.authorization.audit import stage_mutation_audit
from langflow.services.authorization.lifecycle import (
    acquire_identity_mutation_lock,
    stage_identity_mutation,
    validate_identity_mutation,
)
from langflow.services.authorization.policy import (
    TeamMemberState,
    TeamOperation,
    TeamRosterCounts,
    TeamRosterError,
    team_operation_action,
    validate_team_roster,
)
from langflow.services.authorization.team_member_grants import (
    ensure_team_member_grant,
    get_team_member_grant,
    remove_team_member_grant,
)
from langflow.services.database.lock_retry import RetryableTransactionError
from langflow.services.database.models.auth import (
    AuthzShare,
    AuthzTeam,
    AuthzTeamMember,
    AuthzTeamMemberGrant,
    TeamInactivationReason,
    TeamRole,
)
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_authorization_service, get_settings_service

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True, slots=True)
class MemberUpsert:
    user_id: UUID
    role: str = TeamRole.USER.value


@dataclass(frozen=True, slots=True)
class TeamPatch:
    team_name: str | None = None
    adom_name: str | None = None
    description: str | None = None
    description_supplied: bool = False
    is_active: bool | None = None
    member_upserts: tuple[MemberUpsert, ...] = ()
    remove_member_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class TeamMutationResult:
    team: AuthzTeam
    events: tuple[AuthorizationMutation, ...]
    counts: TeamRosterCounts


@dataclass(frozen=True, slots=True)
class MembershipMutationResult:
    member: AuthzTeamMember
    events: tuple[AuthorizationMutation, ...]
    counts: TeamRosterCounts


@dataclass(frozen=True, slots=True)
class TeamActorCapabilities:
    current_user_role: str | None
    can_update: bool
    can_set_active: bool
    can_delete: bool
    can_add_user_member: bool
    can_add_privileged_member: bool
    can_change_roles: bool
    can_remove_user_member: bool


@dataclass(frozen=True, slots=True)
class UserTeamLifecycleResult:
    """Team/share changes staged for an unavoidable user lifecycle event."""

    events: tuple[AuthorizationMutation, ...]
    removed_share_snapshots: tuple[ShareRuleSnapshot, ...]
    deactivated_team_ids: tuple[UUID, ...]
    retired_team_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class UserTeamLifecycleLockHint:
    """Untrusted identifiers used to acquire a user lifecycle lock set."""

    team_ids: tuple[UUID, ...]
    member_ids_by_team: tuple[tuple[UUID, tuple[UUID, ...]], ...]
    affected_user_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class UserTeamLifecycleLockContext:
    """Canonical user/team state retained under the ordered transaction locks."""

    users: dict[UUID, User]
    teams: dict[UUID, AuthzTeam]
    members_by_team: dict[UUID, list[AuthzTeamMember]]


class TeamManagementError(Exception):
    """Stable domain failure translated by the API boundary."""

    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    @property
    def detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class _TeamLockSetChangedError(TeamManagementError, RetryableTransactionError):
    """Request a bounded replay when a preliminary roster hint became stale."""

    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="TEAM_ROSTER_CHANGED",
            message="The team roster changed while the operation was being prepared.",
        )


def _error(status_code: int, code: str, message: str) -> TeamManagementError:
    return TeamManagementError(status_code=status_code, code=code, message=message)


async def _lock_team(session: AsyncSession, team_id: UUID) -> AuthzTeam:
    """Acquire the parent-row write lock before reading the roster."""
    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        # SELECT FOR UPDATE is ignored by SQLite. This no-op write obtains the
        # database write transaction before invariant reads.
        await session.exec(
            update(AuthzTeam).where(col(AuthzTeam.id) == team_id).values(updated_at=AuthzTeam.updated_at)
        )
    statement = (
        select(AuthzTeam).where(AuthzTeam.id == team_id).with_for_update().execution_options(populate_existing=True)
    )
    team = (await session.exec(statement)).first()
    if team is None:
        raise _error(404, "TEAM_NOT_FOUND", "Team not found")
    return team


async def _member_rows(
    session: AsyncSession,
    team_id: UUID,
    *,
    lock: bool = True,
) -> list[AuthzTeamMember]:
    statement = select(AuthzTeamMember).where(AuthzTeamMember.team_id == team_id).order_by(col(AuthzTeamMember.user_id))
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return list((await session.exec(statement)).all())


async def _users_by_id(
    session: AsyncSession,
    user_ids: Sequence[UUID],
    *,
    lock: bool = True,
) -> dict[UUID, User]:
    if not user_ids:
        return {}
    ordered_ids = tuple(sorted(set(user_ids), key=str))
    if lock and session.get_bind().dialect.name == "sqlite":
        # SQLite ignores SELECT FOR UPDATE.  Take its write transaction at the
        # first entity family in the global lock order, before invariant reads.
        await session.exec(update(User).where(col(User.id).in_(ordered_ids)).values(updated_at=User.updated_at))
    statement = select(User).where(col(User.id).in_(ordered_ids)).order_by(col(User.id))
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    users = (await session.exec(statement)).all()
    return {user.id: user for user in users}


async def _active_users_by_id(
    session: AsyncSession,
    user_ids: Sequence[UUID],
    *,
    lock: bool = True,
) -> dict[UUID, User]:
    users = await _users_by_id(session, user_ids, lock=lock)
    return {user_id: user for user_id, user in users.items() if user.is_active is True}


async def _lock_team_state(
    session: AsyncSession,
    team_id: UUID,
    *,
    additional_user_ids: Sequence[UUID] = (),
) -> tuple[AuthzTeam, list[AuthzTeamMember], dict[UUID, User]]:
    """Lock users, the team, then memberships and verify the hinted roster.

    The unlocked identifier read is only a lock-set hint.  Every HTTP writer
    runs through ``run_with_lock_retry``; if another committed writer changed
    the roster before the ordered locks were complete, the whole transaction
    is rolled back and replayed against a fresh hint.
    """
    await acquire_identity_mutation_lock(
        get_authorization_service(), session, kind=AuthorizationMutationKind.TEAM_UPDATED, entity_id=team_id
    )
    sqlite_team: AuthzTeam | None = None
    if session.get_bind().dialect.name == "sqlite":
        # SQLite has one database-wide writer and ignores row-lock ordering.
        # Acquire the parent-row write transaction before even the roster hint
        # so a waiter cannot validate against the snapshot of an earlier
        # writer. PostgreSQL follows the cross-entity row order below.
        sqlite_team = await _lock_team(session, team_id)

    hinted_members = await _member_rows(session, team_id, lock=False)
    hinted_member_ids = {member.user_id for member in hinted_members}
    users = await _active_users_by_id(
        session,
        tuple(hinted_member_ids) + tuple(additional_user_ids),
        lock=True,
    )
    team = sqlite_team if sqlite_team is not None else await _lock_team(session, team_id)
    members = await _member_rows(session, team_id, lock=True)
    if {member.user_id for member in members} != hinted_member_ids:
        raise _TeamLockSetChangedError
    return team, members, users


async def _roster_states(
    session: AsyncSession,
    members: Sequence[AuthzTeamMember],
    *,
    lock: bool = True,
) -> tuple[TeamMemberState, ...]:
    users = await _active_users_by_id(session, [member.user_id for member in members], lock=lock)
    return tuple(
        TeamMemberState(
            user_id=member.user_id,
            role=member.role,
            is_active=member.user_id in users,
        )
        for member in members
    )


async def team_roster_counts(session: AsyncSession, team_id: UUID) -> TeamRosterCounts:
    # Serialization and list views must not acquire mutation locks. Writers
    # call the same helpers with their default lock=True after locking the
    # parent team row.
    members = await _member_rows(session, team_id, lock=False)
    states = await _roster_states(session, members, lock=False)
    active_members = sum(member.is_active for member in states)
    active_admins = sum(member.is_active and member.role == TeamRole.ADMIN.value for member in states)
    return TeamRosterCounts(len(states), active_members, active_admins)


async def team_is_valid_recipient(session: AsyncSession, team_id: UUID, *, lock: bool = False) -> bool:
    """Return whether a team can currently confer access to active users."""
    if lock:
        try:
            team, members, users = await _lock_team_state(session, team_id)
        except TeamManagementError as exc:
            if exc.code == "TEAM_NOT_FOUND":
                return False
            raise
    else:
        team = (await session.exec(select(AuthzTeam).where(AuthzTeam.id == team_id))).first()
        members = await _member_rows(session, team_id, lock=False) if team is not None else []
        users = await _active_users_by_id(
            session,
            [member.user_id for member in members],
            lock=False,
        )
    if team is None or team.is_active is not True:
        return False
    states = tuple(TeamMemberState(member.user_id, member.role, member.user_id in users) for member in members)
    try:
        validate_team_roster(states, team_is_active=True)
    except TeamRosterError:
        return False
    return True


async def _actor_role(session: AsyncSession, *, actor_id: UUID, team_id: UUID) -> str | None:
    statement = select(AuthzTeamMember.role).where(
        AuthzTeamMember.team_id == team_id,
        AuthzTeamMember.user_id == actor_id,
    )
    return (await session.exec(statement)).first()


async def team_actor_capabilities(
    session: AsyncSession,
    *,
    actor: User,
    team_id: UUID,
) -> TeamActorCapabilities:
    return (await team_actor_capabilities_many(session, actor=actor, team_ids=(team_id,)))[team_id]


def actor_can_administer_platform(actor: User | UserRead) -> bool:
    """Apply active-user, configured bypass, and credential-ceiling gates."""
    if actor.is_active is not True or actor.is_superuser is not True:
        return False
    try:
        bypass = bool(getattr(get_settings_service().auth_settings, "AUTHZ_SUPERUSER_BYPASS", True))
    except Exception:  # noqa: BLE001 - administrative capability must fail closed
        return False
    external = get_current_external_access_context()
    return bypass and (external is None or external.level == EXTERNAL_ACCESS_ADMIN)


async def team_actor_capabilities_many(
    session: AsyncSession,
    *,
    actor: User,
    team_ids: Sequence[UUID],
) -> dict[UUID, TeamActorCapabilities]:
    """Batch exact-team probes through the same service that authorizes mutations."""
    actions = (
        "update",
        "set_active",
        "delete",
        "add_member:user",
        "add_member:admin",
        "change_role:user:maintainer",
        "remove_member:user",
    )
    service = get_authorization_service()
    async with service.admission_context(session=session) as snapshot:
        roles = dict(
            (
                await snapshot.exec(
                    select(AuthzTeamMember.team_id, AuthzTeamMember.role).where(
                        AuthzTeamMember.user_id == actor.id, col(AuthzTeamMember.team_id).in_(team_ids)
                    )
                )
            ).all()
        )
        with authorization_session(snapshot, admission=True):
            administrator = await is_administrator(actor, resource="team", authorization_service=service)
            decisions = await service.batch_enforce(
                user_id=actor.id,
                domain="*",
                requests=tuple((f"team:{team_id}", action) for team_id in team_ids for action in actions),
            )
    if len(decisions) != len(team_ids) * len(actions):
        msg = "Authorization service returned an invalid team capability batch."
        raise RuntimeError(msg)
    return {
        team_id: TeamActorCapabilities(
            roles.get(team_id),
            *(
                (administrator or allowed) and external_access_allows("write")
                for allowed in decisions[index * len(actions) : (index + 1) * len(actions)]
            ),
        )
        for index, team_id in enumerate(team_ids)
    }


async def require_team_operation(
    session: AsyncSession,
    *,
    actor: User,
    team_id: UUID,
    operation: TeamOperation,
    target_role: str | None = None,
    new_role: str | None = None,
) -> None:
    action = team_operation_action(operation, target_role=target_role, new_role=new_role)
    if actor.is_active is not True:
        raise _error(403, "TEAM_OPERATION_FORBIDDEN", "An active caller is required.")
    if action is not None:
        if await is_administrator(actor, resource="team", authorization_service=get_authorization_service()):
            return
        with authorization_session(session):
            if await get_authorization_service().enforce(
                user_id=actor.id, domain="*", obj=f"team:{team_id}", act=action
            ):
                return
    raise _error(403, "TEAM_OPERATION_FORBIDDEN", "You cannot perform this operation on the team.")


def _validate_roster_for_mutation(
    states: Sequence[TeamMemberState],
    *,
    is_active: bool,
) -> TeamRosterCounts:
    try:
        return validate_team_roster(states, team_is_active=is_active)
    except TeamRosterError as exc:
        if exc.code == "TEAM_MEMBERS_REQUIRED":
            raise _error(409, "TEAM_LAST_MEMBER", "A team must retain at least one member.") from exc
        if exc.code == "TEAM_ACTIVE_ADMIN_REQUIRED":
            raise _error(
                409,
                "TEAM_LAST_ACTIVE_ADMIN",
                "An active team must retain an active Team Admin.",
            ) from exc
        raise _error(422, exc.code, str(exc)) from exc


async def create_team(
    session: AsyncSession,
    *,
    actor: User,
    team_name: str,
    adom_name: str,
    description: str | None,
    is_active: bool,
    members: Sequence[MemberUpsert],
    operation_id: str | None = None,
) -> TeamMutationResult:
    await acquire_identity_mutation_lock(
        get_authorization_service(), session, kind=AuthorizationMutationKind.TEAM_CREATED
    )
    actor = (await _users_by_id(session, (actor.id,)))[actor.id]
    if not await is_administrator(actor, resource="team", authorization_service=get_authorization_service()):
        raise _error(403, "TEAM_OPERATION_FORBIDDEN", "Platform Admin authority is required.")
    if not members:
        raise _error(422, "TEAM_MEMBERS_REQUIRED", "Initial team members are required.")
    if len({member.user_id for member in members}) != len(members):
        raise _error(409, "TEAM_MEMBERSHIP_EXISTS", "The initial roster contains duplicate users.")

    users = await _active_users_by_id(session, [member.user_id for member in members])
    if len(users) != len(members):
        raise _error(422, "TEAM_MEMBER_INELIGIBLE", "Every initial member must be an active user.")
    states = tuple(TeamMemberState(user_id=member.user_id, role=member.role, is_active=True) for member in members)
    try:
        # Creation always nominates an active Team Admin, including when the
        # team starts administratively inactive.
        counts = validate_team_roster(states, team_is_active=True)
    except TeamRosterError as exc:
        raise _error(422, exc.code, str(exc)) from exc

    now = datetime.now(timezone.utc)
    team = AuthzTeam(
        team_name=team_name,
        adom_name=adom_name,
        description=description,
        is_active=is_active,
        inactivation_reason=None if is_active else TeamInactivationReason.MANUAL.value,
        created_at=now,
        updated_at=now,
    )
    session.add(team)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise _error(409, "TEAM_CONFLICT", "The team already exists.") from exc

    events: list[AuthorizationMutation] = [
        AuthorizationMutation(
            kind=AuthorizationMutationKind.TEAM_CREATED,
            entity_id=team.id,
            actor_user_id=actor.id,
            team_id=team.id,
            affected_user_ids=tuple(member.user_id for member in members),
            policy_relevant_fields=("adom_name", "is_active"),
        )
    ]
    for requested in members:
        member = AuthzTeamMember(
            team_id=team.id,
            user_id=requested.user_id,
            source="manual",
            role=requested.role,
            created_at=now,
            updated_at=now,
        )
        event = AuthorizationMutation(
            kind=AuthorizationMutationKind.TEAM_MEMBER_ADDED,
            entity_id=member.id,
            actor_user_id=actor.id,
            affected_user_ids=(requested.user_id,),
            team_id=team.id,
            policy_relevant_fields=("team_id", "user_id", "source", "role"),
        )
        await validate_identity_mutation(get_authorization_service(), session, event)
        await ensure_team_member_grant(
            session,
            team_id=team.id,
            user_id=member.user_id,
            source_kind="manual",
            administrative_actor=actor.id,
            membership=member,
            membership_is_new=True,
        )
        events.append(event)
        stage_mutation_audit(
            session=session,
            user_id=actor.id,
            action="team_member:add",
            obj=f"team:{team.id}",
            details=administration_audit_details(
                {"user_id": str(requested.user_id), "role": requested.role, "source": "manual"},
                operation_id=operation_id,
            ),
        )

    try:
        await session.flush()
    except IntegrityError as exc:
        raise _error(409, "TEAM_CONFLICT", "The team or one of its memberships already exists.") from exc

    service = get_authorization_service()
    for event in events:
        await stage_identity_mutation(service, session, event)
    stage_mutation_audit(
        session=session,
        user_id=actor.id,
        action="team:create",
        obj=f"team:{team.id}",
        details=administration_audit_details(
            {
                "team_name": team.team_name,
                "member_count": counts.member_count,
                "active_admin_count": counts.active_admin_count,
            },
            operation_id=operation_id,
        ),
    )
    return TeamMutationResult(team, tuple(events), counts)


async def patch_team(
    session: AsyncSession,
    *,
    actor: User,
    team_id: UUID,
    patch: TeamPatch,
    require_absent_member_ids: Sequence[UUID] = (),
    require_present_member_ids: Sequence[UUID] = (),
    operation_id: str | None = None,
) -> TeamMutationResult:
    upsert_ids = [item.user_id for item in patch.member_upserts]
    remove_ids = list(patch.remove_member_ids)
    if len(set(upsert_ids)) != len(upsert_ids) or len(set(remove_ids)) != len(remove_ids):
        raise _error(409, "TEAM_MEMBERSHIP_EXISTS", "Duplicate roster operation.")
    if set(upsert_ids) & set(remove_ids):
        raise _error(422, "TEAM_ROSTER_OPERATION_CONFLICT", "A user cannot be added and removed together.")

    team, current, users = await _lock_team_state(
        session,
        team_id,
        additional_user_ids=(actor.id, *upsert_ids, *remove_ids),
    )
    actor = users.get(actor.id)
    if actor is None:
        raise _error(403, "TEAM_OPERATION_FORBIDDEN", "An active caller is required.")
    current_by_user = {member.user_id: member for member in current}
    for user_id in set(require_absent_member_ids) & set(current_by_user):
        existing = current_by_user[user_id]
        if (
            existing.source == "manual"
            or await get_team_member_grant(session, membership_id=existing.id, source_kind="manual") is not None
        ):
            raise _error(409, "TEAM_MEMBERSHIP_EXISTS", "User is already a manual member of this team.")
    if set(require_present_member_ids) - set(current_by_user):
        raise _error(404, "TEAM_MEMBERSHIP_NOT_FOUND", "Membership not found")

    metadata_change = any(
        (
            patch.team_name is not None,
            patch.adom_name is not None,
            patch.description_supplied,
        )
    )
    if patch.adom_name is not None and not await is_administrator(
        actor, resource="team", authorization_service=get_authorization_service()
    ):
        raise _error(403, "TEAM_OPERATION_FORBIDDEN", "Only a Platform Admin may change the directory mapping.")
    # An empty (or null-only) patch still touches metadata and returns the team.
    # It must not bypass the role checks used by actual metadata updates.
    metadata_only_patch = patch.is_active is None and not (patch.member_upserts or remove_ids)
    if metadata_change or metadata_only_patch:
        await require_team_operation(session, actor=actor, team_id=team_id, operation=TeamOperation.UPDATE)
    if patch.is_active is not None and not await is_administrator(
        actor, resource="team", authorization_service=get_authorization_service()
    ):
        raise _error(403, "TEAM_OPERATION_FORBIDDEN", "Only a Platform Admin may change team status.")

    prospective: dict[UUID, tuple[str, bool]] = {}
    for member in current:
        prospective[member.user_id] = (member.role, member.user_id in users)

    for item in patch.member_upserts:
        existing = current_by_user.get(item.user_id)
        if item.user_id not in users:
            raise _error(422, "TEAM_MEMBER_INELIGIBLE", "Team members must be active users.")
        operation = TeamOperation.ADD_MEMBER if existing is None else TeamOperation.CHANGE_ROLE
        await require_team_operation(
            session,
            actor=actor,
            team_id=team_id,
            operation=operation,
            target_role=existing.role if existing else None,
            new_role=item.role,
        )
        prospective[item.user_id] = (item.role, True)

    for user_id in remove_ids:
        existing = current_by_user.get(user_id)
        if existing is None:
            raise _error(404, "TEAM_MEMBERSHIP_NOT_FOUND", "Membership not found")
        if existing.source != "manual":
            raise _error(
                409,
                "TEAM_MEMBERSHIP_SOURCE_MANAGED",
                "This membership is managed by an authoritative directory.",
            )
        await require_team_operation(
            session,
            actor=actor,
            team_id=team_id,
            operation=TeamOperation.REMOVE_MEMBER,
            target_role=existing.role,
        )
        grants = list(
            (
                await session.exec(
                    select(AuthzTeamMemberGrant).where(AuthzTeamMemberGrant.membership_id == existing.id)
                )
            ).all()
        )
        if not any(grant.source_kind == "manual" for grant in grants):
            raise _error(
                409, "TEAM_MEMBERSHIP_SOURCE_MANAGED", "This membership is managed by an authoritative directory."
            )
        if all(grant.source_kind == "manual" for grant in grants):
            prospective.pop(user_id, None)

    proposed_active = patch.is_active if patch.is_active is not None else team.is_active
    states = tuple(TeamMemberState(user_id, role, active) for user_id, (role, active) in prospective.items())
    counts = _validate_roster_for_mutation(states, is_active=proposed_active)

    now = datetime.now(timezone.utc)
    events: list[AuthorizationMutation] = []
    changed_fields: list[str] = []
    previous_adom = team.adom_name
    if patch.team_name is not None and patch.team_name != team.team_name:
        team.team_name = patch.team_name
        changed_fields.append("team_name")
    if patch.adom_name is not None and patch.adom_name != team.adom_name:
        team.adom_name = patch.adom_name
        changed_fields.append("adom_name")
    if patch.description_supplied and patch.description != team.description:
        team.description = patch.description
        changed_fields.append("description")
    if patch.is_active is not None and patch.is_active != team.is_active:
        team.is_active = patch.is_active
        team.inactivation_reason = None if patch.is_active else TeamInactivationReason.MANUAL.value
        changed_fields.extend(("is_active", "inactivation_reason"))

    for item in patch.member_upserts:
        existing = current_by_user.get(item.user_id)
        if existing is None:
            member = AuthzTeamMember(
                team_id=team.id,
                user_id=item.user_id,
                source="manual",
                role=item.role,
                created_at=now,
                updated_at=now,
            )
            await validate_identity_mutation(
                get_authorization_service(),
                session,
                AuthorizationMutation(
                    kind=AuthorizationMutationKind.TEAM_MEMBER_ADDED,
                    entity_id=member.id,
                    actor_user_id=actor.id,
                    affected_user_ids=(item.user_id,),
                    team_id=team.id,
                    policy_relevant_fields=("team_id", "user_id", "source", "role"),
                ),
            )
            await ensure_team_member_grant(
                session,
                team_id=team.id,
                user_id=member.user_id,
                source_kind="manual",
                administrative_actor=actor.id,
                membership=member,
                membership_is_new=True,
            )
            events.append(
                AuthorizationMutation(
                    kind=AuthorizationMutationKind.TEAM_MEMBER_ADDED,
                    entity_id=member.id,
                    actor_user_id=actor.id,
                    affected_user_ids=(item.user_id,),
                    team_id=team.id,
                    policy_relevant_fields=("team_id", "user_id", "source", "role"),
                )
            )
            stage_mutation_audit(
                session=session,
                user_id=actor.id,
                action="team_member:add",
                obj=f"team:{team.id}",
                details=administration_audit_details(
                    {"user_id": str(item.user_id), "role": item.role, "source": "manual"}, operation_id=operation_id
                ),
            )
            continue
        if item.user_id in require_absent_member_ids:
            await ensure_team_member_grant(
                session,
                team_id=team_id,
                user_id=item.user_id,
                source_kind="manual",
                administrative_actor=actor.id,
                membership=existing,
            )
            stage_mutation_audit(
                session=session,
                user_id=actor.id,
                action="team_member:add",
                obj=f"team:{team.id}",
                details=administration_audit_details(
                    {"user_id": str(item.user_id), "role": item.role, "source": "manual"},
                    operation_id=operation_id,
                ),
            )
        if existing.role != item.role:
            previous_role = existing.role
            existing.role = item.role
            existing.updated_at = now
            events.append(
                AuthorizationMutation(
                    kind=AuthorizationMutationKind.TEAM_MEMBER_ROLE_CHANGED,
                    entity_id=existing.id,
                    actor_user_id=actor.id,
                    affected_user_ids=(item.user_id,),
                    team_id=team.id,
                    policy_relevant_fields=("role",),
                    previous_identifier=previous_role,
                )
            )
            stage_mutation_audit(
                session=session,
                user_id=actor.id,
                action="team_member:role_changed",
                obj=f"team:{team.id}",
                details=administration_audit_details(
                    {"user_id": str(item.user_id), "previous_role": previous_role, "new_role": item.role},
                    operation_id=operation_id,
                ),
            )

    for user_id in remove_ids:
        member = current_by_user[user_id]
        events.append(
            AuthorizationMutation(
                kind=AuthorizationMutationKind.TEAM_MEMBER_REMOVED,
                entity_id=member.id,
                actor_user_id=actor.id,
                affected_user_ids=(user_id,),
                team_id=team.id,
                policy_relevant_fields=("team_id", "user_id", "source", "role"),
            )
        )
        await validate_identity_mutation(get_authorization_service(), session, events[-1])
        await remove_team_member_grant(
            session, team_id=team_id, user_id=user_id, source_kind="manual", membership=member
        )
        stage_mutation_audit(
            session=session,
            user_id=actor.id,
            action="team_member:remove",
            obj=f"team:{team.id}",
            details=administration_audit_details(
                {"user_id": str(user_id), "previous_role": member.role, "source": member.source},
                operation_id=operation_id,
            ),
        )

    if changed_fields:
        events.insert(
            0,
            AuthorizationMutation(
                kind=AuthorizationMutationKind.TEAM_UPDATED,
                entity_id=team.id,
                actor_user_id=actor.id,
                affected_user_ids=tuple(prospective),
                team_id=team.id,
                policy_relevant_fields=tuple(
                    sorted(set(changed_fields) & {"adom_name", "is_active", "inactivation_reason"})
                ),
                previous_identifier=previous_adom if team.adom_name != previous_adom else None,
            ),
        )
    team.updated_at = now
    session.add(team)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise _error(409, "TEAM_CONFLICT", "The requested team change conflicts with current data.") from exc

    service = get_authorization_service()
    for event in events:
        await stage_identity_mutation(service, session, event)
    stage_mutation_audit(
        session=session,
        user_id=actor.id,
        action="team:update",
        obj=f"team:{team.id}",
        details=administration_audit_details(
            {
                "fields_changed": sorted(changed_fields),
                "member_upserts": [str(item.user_id) for item in patch.member_upserts],
                "member_removals": [str(user_id) for user_id in remove_ids],
            },
            operation_id=operation_id,
        ),
    )
    return TeamMutationResult(team, tuple(events), counts)


async def add_member(
    session: AsyncSession,
    *,
    actor: User,
    team_id: UUID,
    member: MemberUpsert,
    operation_id: str | None = None,
) -> MembershipMutationResult:
    result = await patch_team(
        session,
        actor=actor,
        team_id=team_id,
        patch=TeamPatch(member_upserts=(member,)),
        require_absent_member_ids=(member.user_id,),
        operation_id=operation_id,
    )
    created = (
        await session.exec(
            select(AuthzTeamMember).where(
                AuthzTeamMember.team_id == team_id,
                AuthzTeamMember.user_id == member.user_id,
            )
        )
    ).one()
    return MembershipMutationResult(created, result.events, result.counts)


async def change_member_role(
    session: AsyncSession,
    *,
    actor: User,
    team_id: UUID,
    user_id: UUID,
    role: str,
    operation_id: str | None = None,
) -> MembershipMutationResult:
    result = await patch_team(
        session,
        actor=actor,
        team_id=team_id,
        patch=TeamPatch(member_upserts=(MemberUpsert(user_id, role),)),
        require_present_member_ids=(user_id,),
        operation_id=operation_id,
    )
    member = (
        await session.exec(
            select(AuthzTeamMember).where(
                AuthzTeamMember.team_id == team_id,
                AuthzTeamMember.user_id == user_id,
            )
        )
    ).one()
    return MembershipMutationResult(member, result.events, result.counts)


async def remove_member(
    session: AsyncSession,
    *,
    actor: User,
    team_id: UUID,
    user_id: UUID,
    operation_id: str | None = None,
) -> tuple[AuthorizationMutation, ...]:
    result = await patch_team(
        session,
        actor=actor,
        team_id=team_id,
        patch=TeamPatch(remove_member_ids=(user_id,)),
        operation_id=operation_id,
    )
    return result.events


async def delete_team(
    session: AsyncSession,
    *,
    actor: User,
    team_id: UUID,
    reason: str = "manual",
    operation_id: str | None = None,
) -> AuthorizationMutation:
    team, members, users = await _lock_team_state(session, team_id, additional_user_ids=(actor.id,))
    actor = users.get(actor.id)
    if actor is None:
        raise _error(403, "TEAM_OPERATION_FORBIDDEN", "An active caller is required.")
    if not await is_administrator(actor, resource="team", authorization_service=get_authorization_service()):
        raise _error(403, "TEAM_OPERATION_FORBIDDEN", "Only a Platform Admin may delete a team.")
    affected = tuple(member.user_id for member in members)
    share_rows = list(
        (
            await session.exec(
                select(AuthzShare)
                .where(
                    AuthzShare.scope == "team",
                    AuthzShare.target_id == team_id,
                )
                .order_by(col(AuthzShare.id))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    for share in share_rows:
        stage_mutation_audit(
            session=session,
            user_id=actor.id,
            action="share:delete",
            obj=f"{share.resource_type}:{share.resource_id}",
            details=administration_audit_details(
                {
                    "share_id": str(share.id),
                    "scope": share.scope,
                    "target_id": str(team_id),
                    "permission_level": share.permission_level,
                    "revision": share.revision,
                    "reason": "team_deleted",
                },
                operation_id=operation_id,
            ),
        )
    if share_rows:
        await session.exec(delete(AuthzShare).where(col(AuthzShare.id).in_([row.id for row in share_rows])))
    await session.exec(
        delete(AuthzTeamMemberGrant).where(
            col(AuthzTeamMemberGrant.membership_id).in_([member.id for member in members])
        )
    )
    await session.exec(delete(AuthzTeamMember).where(col(AuthzTeamMember.team_id) == team_id))
    await session.delete(team)
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.TEAM_DELETED,
        entity_id=team_id,
        actor_user_id=actor.id,
        affected_user_ids=affected,
        team_id=team_id,
        policy_relevant_fields=("adom_name", "is_active"),
        previous_identifier=team.adom_name,
    )
    await session.flush()
    await stage_identity_mutation(get_authorization_service(), session, mutation)
    stage_mutation_audit(
        session=session,
        user_id=actor.id,
        action="team:delete",
        obj=f"team:{team_id}",
        details=administration_audit_details(
            {
                "team_name": team.team_name,
                "member_count": len(members),
                "reason": reason,
                "team_shares_removed": len(share_rows),
            },
            operation_id=operation_id,
        ),
    )
    return mutation


async def prepare_user_team_lifecycle_lock_hint(
    session: AsyncSession,
    *,
    user_id: UUID,
) -> UserTeamLifecycleLockHint:
    """Read the candidate teams and users without treating them as authority."""
    membership_hints = list(
        (
            await session.exec(
                select(AuthzTeamMember).where(AuthzTeamMember.user_id == user_id).order_by(col(AuthzTeamMember.team_id))
            )
        ).all()
    )
    team_ids = tuple(sorted({row.team_id for row in membership_hints}, key=str))
    member_ids_by_team: list[tuple[UUID, tuple[UUID, ...]]] = []
    affected_user_ids = {user_id}
    for team_id in team_ids:
        members = await _member_rows(session, team_id, lock=False)
        member_ids = tuple(member.user_id for member in members)
        member_ids_by_team.append((team_id, member_ids))
        affected_user_ids.update(member_ids)
    return UserTeamLifecycleLockHint(
        team_ids=team_ids,
        member_ids_by_team=tuple(member_ids_by_team),
        affected_user_ids=tuple(sorted(affected_user_ids, key=str)),
    )


async def acquire_user_team_lifecycle_locks(
    session: AsyncSession,
    *,
    user_id: UUID,
    hint: UserTeamLifecycleLockHint,
) -> UserTeamLifecycleLockContext:
    """Acquire users, teams, and memberships and reject a stale lock-set hint."""
    users = await _users_by_id(session, hint.affected_user_ids, lock=True)

    current_team_ids = tuple(
        sorted(
            (
                await session.exec(
                    select(AuthzTeamMember.team_id)
                    .where(AuthzTeamMember.user_id == user_id)
                    .order_by(col(AuthzTeamMember.team_id))
                )
            ).all(),
            key=str,
        )
    )
    if current_team_ids != hint.team_ids:
        raise _TeamLockSetChangedError

    teams: dict[UUID, AuthzTeam] = {}
    for team_id in hint.team_ids:
        try:
            teams[team_id] = await _lock_team(session, team_id)
        except TeamManagementError as exc:
            if exc.code == "TEAM_NOT_FOUND":
                raise _TeamLockSetChangedError from exc
            raise

    hinted_member_ids = dict(hint.member_ids_by_team)
    members_by_team: dict[UUID, list[AuthzTeamMember]] = {}
    for team_id in hint.team_ids:
        members = await _member_rows(session, team_id)
        if tuple(member.user_id for member in members) != hinted_member_ids[team_id]:
            raise _TeamLockSetChangedError
        members_by_team[team_id] = members

    return UserTeamLifecycleLockContext(users=users, teams=teams, members_by_team=members_by_team)


async def apply_user_team_lifecycle(
    session: AsyncSession,
    *,
    actor_id: UUID,
    user_id: UUID,
    remove_memberships: bool,
    lock_context: UserTeamLifecycleLockContext,
) -> UserTeamLifecycleResult:
    """Preserve team invariants during security-driven user lifecycle changes.

    A disabled user remains a roster member but is no longer an active Admin.
    A deleted user is explicitly removed from every team before the User row is
    deleted, avoiding an unchecked database cascade. Empty teams are retired;
    non-empty active teams without an active Admin are suspended. Resources
    referenced by removed team shares are never touched.
    """
    team_ids = tuple(sorted(lock_context.teams, key=str))
    active_users = {user_id: user for user_id, user in lock_context.users.items() if user.is_active is True}

    now = datetime.now(timezone.utc)
    service = get_authorization_service()
    events: list[AuthorizationMutation] = []
    removed_snapshots: list[ShareRuleSnapshot] = []
    deactivated: list[UUID] = []
    retired: list[UUID] = []

    for team_id in team_ids:
        team = lock_context.teams[team_id]
        members = lock_context.members_by_team[team_id]
        target_members = [member for member in members if member.user_id == user_id]
        prospective = [member for member in members if not remove_memberships or member.user_id != user_id]

        if remove_memberships:
            for member in target_members:
                await session.exec(delete(AuthzTeamMemberGrant).where(AuthzTeamMemberGrant.membership_id == member.id))
                await session.delete(member)
                event = AuthorizationMutation(
                    kind=AuthorizationMutationKind.TEAM_MEMBER_REMOVED,
                    entity_id=member.id,
                    actor_user_id=actor_id,
                    affected_user_ids=(user_id,),
                    team_id=team_id,
                    policy_relevant_fields=("team_id", "user_id", "source", "role"),
                )
                events.append(event)
                stage_mutation_audit(
                    session=session,
                    user_id=actor_id,
                    action="team_member:remove",
                    obj=f"team:{team_id}",
                    details={
                        "user_id": str(user_id),
                        "previous_role": member.role,
                        "source": member.source,
                        "reason": "user_deleted",
                    },
                )

        if not prospective:
            share_rows = list(
                (
                    await session.exec(
                        select(AuthzShare)
                        .where(AuthzShare.scope == "team", AuthzShare.target_id == team_id)
                        .order_by(col(AuthzShare.id))
                        .with_for_update()
                    )
                ).all()
            )
            for share in share_rows:
                removed_snapshots.append(
                    ShareRuleSnapshot(
                        share_id=share.id,
                        resource_type=share.resource_type,
                        resource_id=share.resource_id,
                        scope=share.scope,
                        target_id=share.target_id,
                        permission_level=share.permission_level,
                    )
                )
                stage_mutation_audit(
                    session=session,
                    user_id=actor_id,
                    action="share:delete",
                    obj=f"{share.resource_type}:{share.resource_id}",
                    details={
                        "share_id": str(share.id),
                        "scope": share.scope,
                        "target_id": str(team_id),
                        "permission_level": share.permission_level,
                        "revision": share.revision,
                        "reason": "team_retired",
                    },
                )
            if share_rows:
                await session.exec(delete(AuthzShare).where(col(AuthzShare.id).in_([row.id for row in share_rows])))
            await session.exec(
                delete(AuthzTeamMemberGrant).where(
                    col(AuthzTeamMemberGrant.membership_id).in_([member.id for member in members])
                )
            )
            await session.exec(delete(AuthzTeamMember).where(col(AuthzTeamMember.team_id) == team_id))
            await session.delete(team)
            event = AuthorizationMutation(
                kind=AuthorizationMutationKind.TEAM_DELETED,
                entity_id=team_id,
                actor_user_id=actor_id,
                affected_user_ids=tuple(member.user_id for member in members),
                team_id=team_id,
                policy_relevant_fields=("adom_name", "is_active"),
                previous_identifier=team.adom_name,
            )
            events.append(event)
            retired.append(team_id)
            stage_mutation_audit(
                session=session,
                user_id=actor_id,
                action="team:retire",
                obj=f"team:{team_id}",
                details={
                    "reason": "user_deleted_empty_team",
                    "team_name": team.team_name,
                    "team_shares_removed": len(share_rows),
                },
            )
            continue

        states = [
            TeamMemberState(member.user_id, member.role, member.user_id in active_users) for member in prospective
        ]
        states = [
            TeamMemberState(state.user_id, state.role, False if state.user_id == user_id else state.is_active)
            for state in states
        ]
        has_active_admin = any(state.is_active and state.role == TeamRole.ADMIN.value for state in states)
        if team.is_active is True and not has_active_admin:
            team.is_active = False
            team.inactivation_reason = TeamInactivationReason.NO_ACTIVE_ADMIN.value
            team.updated_at = now
            session.add(team)
            event = AuthorizationMutation(
                kind=AuthorizationMutationKind.TEAM_UPDATED,
                entity_id=team_id,
                actor_user_id=actor_id,
                affected_user_ids=tuple(state.user_id for state in states),
                team_id=team_id,
                policy_relevant_fields=("is_active", "inactivation_reason"),
            )
            events.append(event)
            deactivated.append(team_id)
            stage_mutation_audit(
                session=session,
                user_id=actor_id,
                action="team:deactivate",
                obj=f"team:{team_id}",
                details={"reason": TeamInactivationReason.NO_ACTIVE_ADMIN.value, "trigger_user_id": str(user_id)},
            )

    if remove_memberships:
        user_share_rows = list(
            (
                await session.exec(
                    select(AuthzShare)
                    .where(AuthzShare.scope == "user", AuthzShare.target_id == user_id)
                    .order_by(col(AuthzShare.id))
                    .with_for_update()
                )
            ).all()
        )
        for share in user_share_rows:
            removed_snapshots.append(
                ShareRuleSnapshot(
                    share_id=share.id,
                    resource_type=share.resource_type,
                    resource_id=share.resource_id,
                    scope=share.scope,
                    target_id=share.target_id,
                    permission_level=share.permission_level,
                )
            )
            stage_mutation_audit(
                session=session,
                user_id=actor_id,
                action="share:delete",
                obj=f"{share.resource_type}:{share.resource_id}",
                details={
                    "share_id": str(share.id),
                    "scope": share.scope,
                    "target_id": str(user_id),
                    "permission_level": share.permission_level,
                    "revision": share.revision,
                    "reason": "recipient_user_deleted",
                },
            )
        if user_share_rows:
            await session.exec(delete(AuthzShare).where(col(AuthzShare.id).in_([row.id for row in user_share_rows])))
        await session.exec(update(AuthzShare).where(col(AuthzShare.created_by) == user_id).values(created_by=None))

    await session.flush()
    for event in events:
        await stage_identity_mutation(service, session, event)
    return UserTeamLifecycleResult(
        events=tuple(events),
        removed_share_snapshots=tuple(removed_snapshots),
        deactivated_team_ids=tuple(deactivated),
        retired_team_ids=tuple(retired),
    )
