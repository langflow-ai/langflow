"""Real database contracts for the transaction-owned authorization projection."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.authorization.casbin import store
from langflow.services.authorization.casbin.grammar import Rule
from langflow.services.database.models.auth import (
    AuthzRole,
    AuthzRoleAssignment,
    CasbinRule,
)
from langflow.services.database.models.user.model import User
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.mark.asyncio
async def test_reconciliation_preserves_unchanged_ids_and_removes_duplicates(policy_db):
    """Given duplicate derived rows, reconciliation retains one stable semantic row."""
    rule = Rule("p", f"user:{uuid4()}", "*", "flow/*", "read")
    async with AsyncSession(policy_db, expire_on_commit=False) as session:
        await store.acquire_writer_lock(session)
        first = await store.reconcile_rules(session, (rule,))
        assert (first.inserted, first.deleted) == (1, 0)
        await session.commit()
        original = (await session.exec(select(CasbinRule))).one()
        original_id = original.id
        await session.rollback()
        await store.acquire_writer_lock(session)
        unchanged = await store.reconcile_rules(session, (rule,))
        assert (unchanged.inserted, unchanged.deleted) == (0, 0)
        session.add(CasbinRule(**rule._asdict()))
        await session.flush()
        duplicates = await store.reconcile_rules(session, (rule,))
        assert (duplicates.inserted, duplicates.deleted) == (0, 1)
        await session.commit()
        assert (await session.exec(select(CasbinRule.id))).one() == original_id


@pytest.mark.asyncio
async def test_failed_compile_rolls_back_canonical_and_derived_state(policy_db, monkeypatch):
    """Given a canonical mutation, a compiler failure cannot publish any of it."""
    actor = User(username=str(uuid4()), password=str(uuid4()), is_active=True)
    async with AsyncSession(policy_db, expire_on_commit=False) as session:
        session.add(actor)
        await session.commit()
        actor_id = actor.id

    def unavailable(_snapshot):
        msg = "compiler unavailable"
        raise RuntimeError(msg)

    monkeypatch.setattr(store, "compile_policy", unavailable)
    async with AsyncSession(policy_db) as session:
        await store.acquire_writer_lock(session)
        role = AuthzRole(name=str(uuid4()), permissions=["flow:read"])
        session.add(role)
        session.add(AuthzRoleAssignment(user_id=actor_id, role_id=role.id, domain_type="global"))
        with pytest.raises(RuntimeError, match="compiler unavailable"):
            await store.reconcile_policy(session)
        await session.rollback()
    async with AsyncSession(policy_db) as session:
        assert not (await session.exec(select(AuthzRole))).all()
        assert not (await session.exec(select(CasbinRule))).all()


@pytest.mark.asyncio
async def test_reconcile_requires_early_writer_ownership(policy_db):
    """A late staging call must never silently become an unordered policy writer."""
    async with AsyncSession(policy_db) as session:
        with pytest.raises(RuntimeError, match="writer lock"):
            await store.reconcile_rules(session, ())
