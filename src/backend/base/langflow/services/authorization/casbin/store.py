"""Transaction-owned projection and coherent admission reads using Langflow sessions."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import TYPE_CHECKING, cast

import casbin
from lfx.services.authorization.base import ShareRuleSnapshot
from sqlalchemy import delete, text
from sqlmodel import col, select

from langflow.services.authorization.casbin.compiler import (
    AssignmentSnapshot,
    AssignmentSource,
    PolicySnapshot,
    RoleSnapshot,
    TeamSnapshot,
    compile_policy,
)
from langflow.services.authorization.casbin.grammar import PolicyFormatError, Rule, validate_rule
from langflow.services.authorization.policy import TeamMemberState, validate_team_roster
from langflow.services.authorization.repository import resolve_resources
from langflow.services.database.lock_retry import RetryableTransactionError
from langflow.services.database.models.auth import (
    AuthzRole,
    AuthzRoleAssignment,
    AuthzRoleAssignmentGrant,
    AuthzShare,
    AuthzTeam,
    AuthzTeamMember,
    CasbinRule,
)
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

# ASCII LFAUTHZ. One deterministic database-wide projection lock, never a user key.
PROJECTION_LOCK_ID = 0x4C46415554485A
_WRITER_TRANSACTION = "langflow.authz.projection_writer"
_FILTER_PARAMETER_LIMIT = 300


@dataclass(frozen=True, slots=True)
class Reconciliation:
    inserted: int
    deleted: int
    total: int


def owns_writer_lock(session: AsyncSession) -> bool:
    transaction = session.sync_session.get_transaction()
    return transaction is not None and session.info.get(_WRITER_TRANSACTION) is transaction


async def acquire_writer_lock(session: AsyncSession) -> None:
    """Lock before canonical reads; only the caller ends this transaction.

    SQLite's legacy driver does not BEGIN on SELECT. Inspect the real driver
    transaction, not SQLAlchemy autobegin. An already established unowned read
    snapshot must be restarted by the caller's whole-transaction retry helper.
    """
    if owns_writer_lock(session):
        return
    with session.no_autoflush:
        connection = await session.connection()
        dialect = connection.dialect.name
        if dialect == "postgresql":
            if (await connection.get_isolation_level()) != "READ COMMITTED":
                msg = "Authorization writers require a fresh Read Committed transaction."
                raise RuntimeError(msg)
            await connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            await connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": PROJECTION_LOCK_ID})
        elif dialect == "sqlite":
            raw = await connection.get_raw_connection()
            if raw.driver_connection.in_transaction:
                msg = "Authorization writer must restart the pre-existing SQLite transaction."
                raise RetryableTransactionError(msg)
            await connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            msg = "Authorization projection requires SQLite or PostgreSQL."
            raise RuntimeError(msg)
    session.info[_WRITER_TRANSACTION] = session.sync_session.get_transaction()


async def establish_read_snapshot(session: AsyncSession) -> None:
    """Establish a real database snapshot before any admission reads."""
    if owns_writer_lock(session):
        return
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        if session.in_transaction():
            msg = "Authorization read isolation must be established before canonical reads."
            raise RuntimeError(msg)
        connection = await session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        await connection.execute(text("SET TRANSACTION READ ONLY"))
    elif dialect == "sqlite":
        connection = await session.connection()
        raw = await connection.get_raw_connection()
        if not raw.driver_connection.in_transaction:
            await connection.exec_driver_sql("BEGIN")
    else:
        msg = "Authorization snapshots require SQLite or PostgreSQL."
        raise RuntimeError(msg)


@asynccontextmanager
async def read_snapshot() -> AsyncIterator[AsyncSession]:
    """Use the existing session infrastructure, never an independent pool."""
    from lfx.services.deps import session_scope_readonly

    async with session_scope_readonly() as raw_session:
        session = cast("AsyncSession", raw_session)
        await establish_read_snapshot(session)
        yield session


async def canonical_snapshot(session: AsyncSession, *, validate_teams: bool = False) -> PolicySnapshot:
    """Load complete non-secret compiler inputs from the caller's ordered transaction."""
    from langflow.services.authorization.repository import ResourceRecord

    active_users = frozenset((await session.exec(select(User.id).where(User.is_active == True))).all())  # noqa: E712
    roles = (await session.exec(select(AuthzRole).execution_options(populate_existing=True))).all()
    assignments = (await session.exec(select(AuthzRoleAssignment).execution_options(populate_existing=True))).all()
    grants = (await session.exec(select(AuthzRoleAssignmentGrant))).all()
    teams = (await session.exec(select(AuthzTeam).execution_options(populate_existing=True))).all()
    memberships = (await session.exec(select(AuthzTeamMember).execution_options(populate_existing=True))).all()
    shares = (await session.exec(select(AuthzShare).execution_options(populate_existing=True))).all()
    # Projects determine role/workspace intersections even without any shares.
    projects = (await session.exec(select(Folder.id, Folder.user_id, Folder.workspace_id, Folder.name))).all()
    resources = [ResourceRecord("project", row.id, row.user_id, row.id, row.workspace_id, row.name) for row in projects]
    resource_ids: dict[str, list[UUID]] = {}
    for share in shares:
        if share.resource_type != "project" and share.scope in {"user", "team"}:
            resource_ids.setdefault(share.resource_type, []).append(share.resource_id)
    for resource_type, ids in resource_ids.items():
        resources.extend((await resolve_resources(session, resource_type=resource_type, resource_ids=ids)).values())
    sources_by_assignment: dict[UUID, list[AssignmentSource]] = {}
    for grant in grants:
        sources_by_assignment.setdefault(grant.assignment_id, []).append(
            AssignmentSource(grant.source_kind, grant.provider_id, grant.external_group)
        )
    members_by_team: dict[UUID, list[TeamMemberState]] = {}
    for member in memberships:
        members_by_team.setdefault(member.team_id, []).append(
            TeamMemberState(member.user_id, member.role, member.user_id in active_users)
        )
    team_snapshots = tuple(
        TeamSnapshot(team.id, team.is_active, tuple(members_by_team.get(team.id, ()))) for team in teams
    )
    if validate_teams:
        for team in team_snapshots:
            validate_team_roster(team.members, team_is_active=team.is_active)
    return PolicySnapshot(
        active_user_ids=active_users,
        roles=tuple(
            RoleSnapshot(row.id, tuple(row.permissions), row.parent_role_id, row.workspace_id) for row in roles
        ),
        assignments=tuple(
            AssignmentSnapshot(
                row.id,
                row.user_id,
                row.role_id,
                row.domain_type,
                row.domain_id,
                tuple(sources_by_assignment.get(row.id, ())),
            )
            for row in assignments
        ),
        teams=team_snapshots,
        shares=tuple(
            ShareRuleSnapshot(
                row.id, row.resource_type, row.resource_id, row.scope, row.target_id, row.permission_level
            )
            for row in shares
        ),
        resources=tuple(resources),
    )


def semantic_rule(row: CasbinRule) -> Rule:
    rule = Rule(row.ptype, row.v0, row.v1, row.v2, row.v3, row.v4, row.v5)
    validate_rule(rule)
    return rule


async def reconcile_rules(
    session: AsyncSession, wanted: Sequence[Rule], *, replace_invalid: bool = False
) -> Reconciliation:
    """Differential persistence with stable row IDs and deterministic deduplication."""
    if not owns_writer_lock(session):
        msg = "Authorization reconciliation requires the early writer lock."
        raise RuntimeError(msg)
    desired = set(wanted)
    for rule in desired:
        validate_rule(rule)
    rows = (await session.exec(select(CasbinRule).order_by(CasbinRule.id))).all()
    retained: set[Rule] = set()
    deleted: list[int] = []
    for row in rows:
        try:
            rule = semantic_rule(row)
        except PolicyFormatError:
            if not replace_invalid:
                raise
            deleted.append(row.id)
            continue
        if rule in desired and rule not in retained:
            retained.add(rule)
        else:
            deleted.append(row.id)
    # Bounded IN lists work with SQLite's lower supported parameter limit.
    for offset in range(0, len(deleted), 500):
        await session.exec(delete(CasbinRule).where(col(CasbinRule.id).in_(deleted[offset : offset + 500])))
    added = desired - retained
    session.add_all(CasbinRule(**rule._asdict()) for rule in sorted(added))
    await session.flush()
    return Reconciliation(len(added), len(deleted), len(desired))


async def verify_projection(session: AsyncSession) -> dict[str, int | bool]:
    """Offline verification only; admission never compiles all canonical policy."""
    wanted = set(compile_policy(await canonical_snapshot(session, validate_teams=True)))
    rows = (await session.exec(select(CasbinRule))).all()
    valid: list[Rule] = []
    invalid = 0
    for row in rows:
        try:
            valid.append(semantic_rule(row))
        except PolicyFormatError:
            invalid += 1
    missing = len(wanted - set(valid))
    unexpected = len(set(valid) - wanted)
    duplicates = len(valid) - len(set(valid))
    return {
        "valid": not (invalid or missing or unexpected or duplicates),
        "canonical_rules": len(wanted),
        "missing": missing,
        "unexpected": unexpected,
        "duplicates": duplicates,
        "invalid": invalid,
    }


async def reconcile_policy(session: AsyncSession, *, validate_teams: bool = False) -> Reconciliation:
    if not owns_writer_lock(session):
        msg = "Authorization reconciliation requires the early writer lock."
        raise RuntimeError(msg)
    await session.flush()
    wanted = compile_policy(await canonical_snapshot(session, validate_teams=validate_teams))
    return await reconcile_rules(session, wanted)


@lru_cache(maxsize=1)
def model_text() -> str:
    return files("langflow.services.authorization.casbin").joinpath("model.conf").read_text(encoding="utf-8")


def enforcer_for(rules: Sequence[Rule]) -> casbin.Enforcer:
    """Build privately, validate completely, and expose only after all rules load."""
    for rule in rules:
        validate_rule(rule)
    model = casbin.Model()
    model.load_model_from_text(model_text())
    enforcer = casbin.Enforcer(model)
    enforcer.enable_auto_save(auto_save=False)
    for rule in rules:
        if rule.ptype == "g":
            enforcer.add_grouping_policy(rule.v0, rule.v1)
        else:
            enforcer.add_policy(rule.v0, rule.v1, rule.v2, rule.v3)
    return enforcer


async def load_rules(
    session: AsyncSession,
    *,
    user_id: UUID,
    domains: Sequence[str] | None = None,
    objects: Sequence[str] | None = None,
) -> tuple[Rule, ...]:
    """Load direct policies and both group kinds within the same database snapshot.

    Omitting object/domain filters serves compact visibility queries for one
    caller. It never loads the whole installation's projection per resource.
    """
    subject = f"user:{user_id}"
    grouping = (await session.exec(select(CasbinRule).where(CasbinRule.ptype == "g", CasbinRule.v0 == subject))).all()
    rules = [semantic_rule(row) for row in grouping]
    subjects = (subject, *(rule.v1 for rule in rules))
    domain_filter = set(domains) | {"*"} if domains is not None else None
    object_filter = set(objects) if objects is not None else None
    for offset in range(0, len(subjects), 200):
        statement = select(CasbinRule).where(
            CasbinRule.ptype == "p", col(CasbinRule.v0).in_(subjects[offset : offset + 200])
        )
        if domains is not None and len(domains) <= _FILTER_PARAMETER_LIMIT:
            statement = statement.where(col(CasbinRule.v1).in_(set(domains) | {"*"}))
        if objects is not None and len(objects) <= _FILTER_PARAMETER_LIMIT:
            statement = statement.where(col(CasbinRule.v2).in_(objects))
        rows = (await session.exec(statement)).all()
        validated = tuple(semantic_rule(row) for row in rows)
        rules.extend(
            rule
            for rule in validated
            if (domain_filter is None or rule.v1 in domain_filter)
            and (object_filter is None or rule.v2 in object_filter)
        )
    return tuple(sorted(set(rules)))
