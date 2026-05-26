"""Tests for authorization plugin models against a real database."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from langflow.services.database.models.auth import (
    AuthzAuditLog,
    AuthzEditLock,
    AuthzRole,
    AuthzRoleAssignment,
    AuthzShare,
    AuthzTeam,
    AuthzTeamMember,
    CasbinRule,
    SharePermissionLevel,
    ShareScope,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


@pytest.fixture(name="authz_db_engine")
def authz_db_engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    yield engine
    engine.sync_engine.dispose()


@pytest.fixture(name="authz_async_session")
async def authz_async_session(authz_db_engine):
    from sqlmodel import SQLModel

    async with authz_db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(authz_db_engine, expire_on_commit=False) as session:
        yield session
    async with authz_db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await authz_db_engine.dispose()


@pytest.mark.anyio
async def test_create_casbin_rule_and_authz_role(authz_async_session: AsyncSession):
    user = User(username="authz_user", password=_TEST_PASSWORD)
    authz_async_session.add(user)
    await authz_async_session.commit()
    await authz_async_session.refresh(user)

    rule = CasbinRule(ptype="p", v0="role:viewer", v1="*", v2="flow:*", v3="read")
    role = AuthzRole(name="viewer", is_system=True, permissions=["flow:read"], created_by=user.id)
    team = AuthzTeam(team_name="Atlas", adom_name="AtlasPlanners")

    authz_async_session.add(rule)
    authz_async_session.add(role)
    authz_async_session.add(team)
    await authz_async_session.commit()

    stored_rule = (await authz_async_session.exec(select(CasbinRule).where(CasbinRule.ptype == "p"))).first()
    stored_role = (await authz_async_session.exec(select(AuthzRole).where(AuthzRole.name == "viewer"))).first()
    assert stored_rule is not None
    assert stored_rule.v3 == "read"
    assert stored_role is not None
    assert stored_role.permissions == ["flow:read"]


@pytest.mark.anyio
async def test_authz_role_assignment_persists(authz_async_session: AsyncSession):
    """AuthzRoleAssignment persists with FK references to user and role."""
    user = User(username="assignee", password=_TEST_PASSWORD)
    assigner = User(username="assigner", password=_TEST_PASSWORD)
    authz_async_session.add_all([user, assigner])
    await authz_async_session.commit()
    await authz_async_session.refresh(user)
    await authz_async_session.refresh(assigner)

    role = AuthzRole(name="editor", permissions=["flow:write"])
    authz_async_session.add(role)
    await authz_async_session.commit()
    await authz_async_session.refresh(role)

    assignment = AuthzRoleAssignment(
        user_id=user.id,
        role_id=role.id,
        domain_type="global",
        assigned_by=assigner.id,
    )
    authz_async_session.add(assignment)
    await authz_async_session.commit()

    stored = (
        await authz_async_session.exec(select(AuthzRoleAssignment).where(AuthzRoleAssignment.user_id == user.id))
    ).first()
    assert stored is not None
    assert stored.role_id == role.id
    assert stored.assigned_by == assigner.id
    assert stored.domain_type == "global"
    assert stored.domain_id is None


@pytest.mark.anyio
async def test_authz_role_assignment_blocks_duplicate_global(authz_async_session: AsyncSession):
    """Two global assignments with the same (user_id, role_id) must conflict.

    Regression for PR #13153 review: the original UNIQUE(user_id, role_id,
    domain_type, domain_id) constraint did not catch this because NULL != NULL
    in SQL. The replacement is a partial unique index keyed on
    (user_id, role_id, domain_type) with a WHERE on the global+NULL case.
    """
    from sqlalchemy.exc import IntegrityError

    user = User(username="dupe_assignee", password=_TEST_PASSWORD)
    authz_async_session.add(user)
    await authz_async_session.commit()
    await authz_async_session.refresh(user)

    role = AuthzRole(name="dupe_editor", permissions=["flow:write"])
    authz_async_session.add(role)
    await authz_async_session.commit()
    await authz_async_session.refresh(role)

    authz_async_session.add(AuthzRoleAssignment(user_id=user.id, role_id=role.id, domain_type="global"))
    await authz_async_session.commit()

    authz_async_session.add(AuthzRoleAssignment(user_id=user.id, role_id=role.id, domain_type="global"))
    with pytest.raises(IntegrityError) as excinfo:
        await authz_async_session.commit()
    # Assert the *specific* constraint fires (the partial unique index over
    # user_id+role_id+domain_type, WHERE domain_id IS NULL) — otherwise a
    # generic NOT NULL or random regression could mask the missing partial
    # index. SQLite reports column names rather than the constraint name; we
    # inspect only the failure clause before ``[SQL: ...]`` (which echoes every
    # column in the INSERT and would otherwise smuggle ``domain_id`` in).
    failure_clause = str(excinfo.value).lower().split("[sql:")[0]
    assert "unique constraint failed" in failure_clause
    assert "domain_type" in failure_clause
    # Unscoped index does not cover domain_id; its absence distinguishes it
    # from the scoped index (which also lists ``domain_id``).
    assert "domain_id" not in failure_clause
    await authz_async_session.rollback()


@pytest.mark.anyio
async def test_authz_role_assignment_blocks_duplicate_non_global_with_null_domain_id(
    authz_async_session: AsyncSession,
):
    """A row with ``domain_type='org' AND domain_id IS NULL`` must still be uniquely constrained.

    Regression for PR #13153 review: the previous ``uq_authz_role_assignment_global``
    partial index filtered on ``domain_type = 'global'`` AND ``domain_id IS NULL``,
    so duplicates with any other ``domain_type`` value plus NULL ``domain_id`` slipped
    past. The widened ``uq_authz_role_assignment_unscoped`` index filters on
    ``domain_id IS NULL`` only, covering every ill-formed combination.
    """
    from sqlalchemy.exc import IntegrityError

    user = User(username="org_dupe_assignee", password=_TEST_PASSWORD)
    authz_async_session.add(user)
    await authz_async_session.commit()
    await authz_async_session.refresh(user)

    role = AuthzRole(name="org_editor", permissions=["flow:write"])
    authz_async_session.add(role)
    await authz_async_session.commit()
    await authz_async_session.refresh(role)

    authz_async_session.add(AuthzRoleAssignment(user_id=user.id, role_id=role.id, domain_type="org"))
    await authz_async_session.commit()

    authz_async_session.add(AuthzRoleAssignment(user_id=user.id, role_id=role.id, domain_type="org"))
    with pytest.raises(IntegrityError) as excinfo:
        await authz_async_session.commit()
    failure_clause = str(excinfo.value).lower().split("[sql:")[0]
    assert "unique constraint failed" in failure_clause
    assert "domain_type" in failure_clause
    # Widened (unscoped) partial index — domain_id is NOT part of the constraint key.
    assert "domain_id" not in failure_clause
    await authz_async_session.rollback()


@pytest.mark.anyio
async def test_authz_role_assignment_blocks_duplicate_scoped(authz_async_session: AsyncSession):
    """Scoped (non-NULL domain_id) duplicates must also conflict via the second partial index."""
    from uuid import uuid4

    from sqlalchemy.exc import IntegrityError

    user = User(username="scoped_assignee", password=_TEST_PASSWORD)
    authz_async_session.add(user)
    await authz_async_session.commit()
    await authz_async_session.refresh(user)

    role = AuthzRole(name="scoped_editor", permissions=["flow:write"])
    authz_async_session.add(role)
    await authz_async_session.commit()
    await authz_async_session.refresh(role)

    workspace_id = uuid4()
    authz_async_session.add(
        AuthzRoleAssignment(user_id=user.id, role_id=role.id, domain_type="workspace", domain_id=workspace_id)
    )
    await authz_async_session.commit()

    authz_async_session.add(
        AuthzRoleAssignment(user_id=user.id, role_id=role.id, domain_type="workspace", domain_id=workspace_id)
    )
    with pytest.raises(IntegrityError) as excinfo:
        await authz_async_session.commit()
    failure_clause = str(excinfo.value).lower().split("[sql:")[0]
    assert "unique constraint failed" in failure_clause
    # The scoped index covers domain_id — its presence distinguishes it from the unscoped one.
    assert "domain_id" in failure_clause
    await authz_async_session.rollback()


@pytest.mark.anyio
async def test_authz_role_assignment_allows_distinct_workspaces(authz_async_session: AsyncSession):
    """Same (user, role) assigned to two different workspaces is legitimate and must persist."""
    from uuid import uuid4

    user = User(username="multi_workspace", password=_TEST_PASSWORD)
    authz_async_session.add(user)
    await authz_async_session.commit()
    await authz_async_session.refresh(user)

    role = AuthzRole(name="multi_editor", permissions=["flow:write"])
    authz_async_session.add(role)
    await authz_async_session.commit()
    await authz_async_session.refresh(role)

    authz_async_session.add(
        AuthzRoleAssignment(user_id=user.id, role_id=role.id, domain_type="workspace", domain_id=uuid4())
    )
    authz_async_session.add(
        AuthzRoleAssignment(user_id=user.id, role_id=role.id, domain_type="workspace", domain_id=uuid4())
    )
    await authz_async_session.commit()

    rows = (
        await authz_async_session.exec(select(AuthzRoleAssignment).where(AuthzRoleAssignment.user_id == user.id))
    ).all()
    assert len(rows) == 2


@pytest.mark.anyio
async def test_authz_team_persists(authz_async_session: AsyncSession):
    """AuthzTeam round-trips through the database with default flags."""
    team = AuthzTeam(team_name="Platform", adom_name="platform-adom", description="Platform team")
    authz_async_session.add(team)
    await authz_async_session.commit()

    stored = (await authz_async_session.exec(select(AuthzTeam).where(AuthzTeam.adom_name == "platform-adom"))).first()
    assert stored is not None
    assert stored.team_name == "Platform"
    assert stored.is_active is True
    assert stored.description == "Platform team"


@pytest.mark.anyio
async def test_authz_team_member_persists(authz_async_session: AsyncSession):
    """AuthzTeamMember persists with FK references to team and user."""
    user = User(username="team_member", password=_TEST_PASSWORD)
    team = AuthzTeam(team_name="Ops", adom_name="ops-adom")
    authz_async_session.add_all([user, team])
    await authz_async_session.commit()
    await authz_async_session.refresh(user)
    await authz_async_session.refresh(team)

    member = AuthzTeamMember(team_id=team.id, user_id=user.id, source="sso")
    authz_async_session.add(member)
    await authz_async_session.commit()

    stored = (await authz_async_session.exec(select(AuthzTeamMember).where(AuthzTeamMember.team_id == team.id))).first()
    assert stored is not None
    assert stored.user_id == user.id
    assert stored.source == "sso"


@pytest.mark.anyio
async def test_authz_share_persists(authz_async_session: AsyncSession):
    """AuthzShare persists with the expected scope and permission level."""
    user = User(username="sharer", password=_TEST_PASSWORD)
    target = User(username="share_target", password=_TEST_PASSWORD)
    authz_async_session.add_all([user, target])
    await authz_async_session.commit()
    await authz_async_session.refresh(user)
    await authz_async_session.refresh(target)

    flow = Flow(name="shared-flow", data={"nodes": []}, user_id=user.id)
    authz_async_session.add(flow)
    await authz_async_session.commit()
    await authz_async_session.refresh(flow)

    share = AuthzShare(
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=target.id,
        permission_level=SharePermissionLevel.WRITE.value,
        created_by=user.id,
    )
    authz_async_session.add(share)
    await authz_async_session.commit()

    stored = (await authz_async_session.exec(select(AuthzShare).where(AuthzShare.resource_id == flow.id))).first()
    assert stored is not None
    assert stored.scope == ShareScope.USER.value
    assert stored.permission_level == SharePermissionLevel.WRITE.value
    assert stored.target_id == target.id


@pytest.mark.anyio
async def test_authz_share_blocks_duplicate_targeted(authz_async_session: AsyncSession):
    """Two USER shares with the same (resource, scope, target_id) must conflict.

    Covered by the ``uq_authz_share_targeted`` partial unique index
    (WHERE target_id IS NOT NULL).
    """
    from sqlalchemy.exc import IntegrityError

    user = User(username="dupe_sharer", password=_TEST_PASSWORD)
    target = User(username="dupe_target", password=_TEST_PASSWORD)
    authz_async_session.add_all([user, target])
    await authz_async_session.commit()
    await authz_async_session.refresh(user)
    await authz_async_session.refresh(target)

    flow = Flow(name="dupe-shared-flow", data={"nodes": []}, user_id=user.id)
    authz_async_session.add(flow)
    await authz_async_session.commit()
    await authz_async_session.refresh(flow)

    authz_async_session.add(
        AuthzShare(
            resource_type="flow",
            resource_id=flow.id,
            scope=ShareScope.USER.value,
            target_id=target.id,
            permission_level=SharePermissionLevel.READ.value,
            created_by=user.id,
        )
    )
    await authz_async_session.commit()

    authz_async_session.add(
        AuthzShare(
            resource_type="flow",
            resource_id=flow.id,
            scope=ShareScope.USER.value,
            target_id=target.id,
            permission_level=SharePermissionLevel.WRITE.value,
            created_by=user.id,
        )
    )
    with pytest.raises(IntegrityError) as excinfo:
        await authz_async_session.commit()
    failure_clause = str(excinfo.value).lower().split("[sql:")[0]
    assert "unique constraint failed" in failure_clause
    # targeted index covers target_id; untargeted does not
    assert "target_id" in failure_clause
    await authz_async_session.rollback()


@pytest.mark.anyio
async def test_authz_share_blocks_duplicate_untargeted(authz_async_session: AsyncSession):
    """Two PUBLIC shares on the same resource must conflict despite NULL target_id.

    Regression for PR #13153 review: the original
    UNIQUE(resource_type, resource_id, scope, target_id) constraint did not
    catch this because NULL != NULL in SQL. Covered by the
    ``uq_authz_share_untargeted`` partial unique index (WHERE target_id IS NULL).
    """
    from sqlalchemy.exc import IntegrityError

    user = User(username="public_sharer", password=_TEST_PASSWORD)
    authz_async_session.add(user)
    await authz_async_session.commit()
    await authz_async_session.refresh(user)

    flow = Flow(name="public-flow", data={"nodes": []}, user_id=user.id)
    authz_async_session.add(flow)
    await authz_async_session.commit()
    await authz_async_session.refresh(flow)

    authz_async_session.add(
        AuthzShare(
            resource_type="flow",
            resource_id=flow.id,
            scope=ShareScope.PUBLIC.value,
            permission_level=SharePermissionLevel.READ.value,
            created_by=user.id,
        )
    )
    await authz_async_session.commit()

    authz_async_session.add(
        AuthzShare(
            resource_type="flow",
            resource_id=flow.id,
            scope=ShareScope.PUBLIC.value,
            permission_level=SharePermissionLevel.WRITE.value,
            created_by=user.id,
        )
    )
    with pytest.raises(IntegrityError) as excinfo:
        await authz_async_session.commit()
    failure_clause = str(excinfo.value).lower().split("[sql:")[0]
    assert "unique constraint failed" in failure_clause
    # The untargeted index covers (resource_type, resource_id, scope) — no target_id column.
    assert "target_id" not in failure_clause
    assert "scope" in failure_clause
    await authz_async_session.rollback()


@pytest.mark.anyio
async def test_authz_share_allows_distinct_targets(authz_async_session: AsyncSession):
    """Same (resource, scope) shared with two different users must persist."""
    user = User(username="multi_share_owner", password=_TEST_PASSWORD)
    alice = User(username="alice_target", password=_TEST_PASSWORD)
    bob = User(username="bob_target", password=_TEST_PASSWORD)
    authz_async_session.add_all([user, alice, bob])
    await authz_async_session.commit()
    await authz_async_session.refresh(user)
    await authz_async_session.refresh(alice)
    await authz_async_session.refresh(bob)

    flow = Flow(name="multi-share-flow", data={"nodes": []}, user_id=user.id)
    authz_async_session.add(flow)
    await authz_async_session.commit()
    await authz_async_session.refresh(flow)

    authz_async_session.add(
        AuthzShare(
            resource_type="flow",
            resource_id=flow.id,
            scope=ShareScope.USER.value,
            target_id=alice.id,
            permission_level=SharePermissionLevel.READ.value,
            created_by=user.id,
        )
    )
    authz_async_session.add(
        AuthzShare(
            resource_type="flow",
            resource_id=flow.id,
            scope=ShareScope.USER.value,
            target_id=bob.id,
            permission_level=SharePermissionLevel.READ.value,
            created_by=user.id,
        )
    )
    await authz_async_session.commit()

    rows = (await authz_async_session.exec(select(AuthzShare).where(AuthzShare.resource_id == flow.id))).all()
    assert len(rows) == 2


@pytest.mark.anyio
async def test_authz_share_rejects_unknown_scope(authz_async_session: AsyncSession):
    """``scope`` must be one of the documented enum values — ``ck_authz_share_scope_enum``."""
    from sqlalchemy.exc import IntegrityError

    user = User(username="invalid_scope_sharer", password=_TEST_PASSWORD)
    authz_async_session.add(user)
    await authz_async_session.commit()
    await authz_async_session.refresh(user)

    flow = Flow(name="invalid-scope-flow", data={"nodes": []}, user_id=user.id)
    authz_async_session.add(flow)
    await authz_async_session.commit()
    await authz_async_session.refresh(flow)

    authz_async_session.add(
        AuthzShare(
            resource_type="flow",
            resource_id=flow.id,
            scope="PRIVATE",  # typo that the lowercase enum doesn't cover
            target_id=None,
            permission_level=SharePermissionLevel.READ.value,
            created_by=user.id,
        )
    )
    with pytest.raises(IntegrityError) as excinfo:
        await authz_async_session.commit()
    assert "ck_authz_share_scope_enum" in str(excinfo.value).lower()
    await authz_async_session.rollback()


@pytest.mark.anyio
async def test_authz_share_rejects_targeted_with_null_target(authz_async_session: AsyncSession):
    """USER/TEAM scopes require a non-NULL target_id — ``ck_authz_share_scope_target_consistency``."""
    from sqlalchemy.exc import IntegrityError

    user = User(username="mismatched_share_sharer", password=_TEST_PASSWORD)
    authz_async_session.add(user)
    await authz_async_session.commit()
    await authz_async_session.refresh(user)

    flow = Flow(name="mismatched-share-flow", data={"nodes": []}, user_id=user.id)
    authz_async_session.add(flow)
    await authz_async_session.commit()
    await authz_async_session.refresh(flow)

    authz_async_session.add(
        AuthzShare(
            resource_type="flow",
            resource_id=flow.id,
            scope=ShareScope.USER.value,
            target_id=None,  # USER without a target is invalid
            permission_level=SharePermissionLevel.READ.value,
            created_by=user.id,
        )
    )
    with pytest.raises(IntegrityError) as excinfo:
        await authz_async_session.commit()
    assert "ck_authz_share_scope_target_consistency" in str(excinfo.value).lower()
    await authz_async_session.rollback()


@pytest.mark.anyio
async def test_authz_share_rejects_untargeted_with_target(authz_async_session: AsyncSession):
    """PRIVATE/PUBLIC scopes forbid target_id — ``ck_authz_share_scope_target_consistency``."""
    from sqlalchemy.exc import IntegrityError

    user = User(username="public_with_target_sharer", password=_TEST_PASSWORD)
    target = User(username="public_with_target_recipient", password=_TEST_PASSWORD)
    authz_async_session.add_all([user, target])
    await authz_async_session.commit()
    await authz_async_session.refresh(user)
    await authz_async_session.refresh(target)

    flow = Flow(name="public-with-target-flow", data={"nodes": []}, user_id=user.id)
    authz_async_session.add(flow)
    await authz_async_session.commit()
    await authz_async_session.refresh(flow)

    authz_async_session.add(
        AuthzShare(
            resource_type="flow",
            resource_id=flow.id,
            scope=ShareScope.PUBLIC.value,
            target_id=target.id,  # PUBLIC with a target is invalid
            permission_level=SharePermissionLevel.READ.value,
            created_by=user.id,
        )
    )
    with pytest.raises(IntegrityError) as excinfo:
        await authz_async_session.commit()
    assert "ck_authz_share_scope_target_consistency" in str(excinfo.value).lower()
    await authz_async_session.rollback()


@pytest.mark.anyio
async def test_authz_edit_lock_persists(authz_async_session: AsyncSession):
    """AuthzEditLock persists with an expiry timestamp tied to a flow + user."""
    user = User(username="lock_holder", password=_TEST_PASSWORD)
    authz_async_session.add(user)
    await authz_async_session.commit()
    await authz_async_session.refresh(user)

    flow = Flow(name="locked-flow", data={"nodes": []}, user_id=user.id)
    authz_async_session.add(flow)
    await authz_async_session.commit()
    await authz_async_session.refresh(flow)

    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    lock = AuthzEditLock(flow_id=flow.id, holder_user_id=user.id, expires_at=expires)
    authz_async_session.add(lock)
    await authz_async_session.commit()

    stored = (await authz_async_session.exec(select(AuthzEditLock).where(AuthzEditLock.flow_id == flow.id))).first()
    assert stored is not None
    assert stored.holder_user_id == user.id
    assert stored.expires_at == expires


@pytest.mark.anyio
async def test_authz_audit_log_persists(authz_async_session: AsyncSession):
    """AuthzAuditLog round-trips with JSON details and an indexed timestamp."""
    user = User(username="audit_subject", password=_TEST_PASSWORD)
    authz_async_session.add(user)
    await authz_async_session.commit()
    await authz_async_session.refresh(user)

    flow = Flow(name="audited-flow", data={"nodes": []}, user_id=user.id)
    authz_async_session.add(flow)
    await authz_async_session.commit()
    await authz_async_session.refresh(flow)

    entry = AuthzAuditLog(
        user_id=user.id,
        action="flow:write",
        resource_type="flow",
        resource_id=flow.id,
        result="allow",
        details={"ip": "127.0.0.1"},
    )
    authz_async_session.add(entry)
    await authz_async_session.commit()

    stored = (await authz_async_session.exec(select(AuthzAuditLog).where(AuthzAuditLog.user_id == user.id))).first()
    assert stored is not None
    assert stored.action == "flow:write"
    assert stored.result == "allow"
    assert stored.details == {"ip": "127.0.0.1"}
    assert stored.timestamp is not None
