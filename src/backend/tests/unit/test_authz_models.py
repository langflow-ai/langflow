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
