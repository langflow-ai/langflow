"""Tests for authorization plugin models against a real database."""

from __future__ import annotations

import pytest
from langflow.services.database.models.auth import (
    AuthzRole,
    AuthzTeam,
    CasbinRule,
)
from langflow.services.database.models.user.model import User
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

_TEST_PASSWORD = "hashed"  # noqa: S105


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
