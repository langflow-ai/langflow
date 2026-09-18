"""Lease semantics: one holder at a time, failover only after expiry."""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.database.models.trigger.model import TriggerEvent
from langflow.services.database.models.trigger.schemas import TriggerEventState
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher, leases, ledger
from langflow.services.triggers.constants import DISPATCHER_LEASE_NAME
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster


async def test_only_one_owner_holds_a_named_lease(client) -> None:  # noqa: ARG001
    async with session_scope() as session:
        first = await leases.acquire(session, name="test-lease", owner="alpha", ttl_s=60)
    async with session_scope() as session:
        second = await leases.acquire(session, name="test-lease", owner="beta", ttl_s=60)
        who = await leases.holder(session, name="test-lease")

    assert first is True
    assert second is False
    assert who == "alpha"


async def test_the_holder_renews_and_a_rival_takes_over_only_after_expiry(client) -> None:  # noqa: ARG001
    async with session_scope() as session:
        assert await leases.acquire(session, name="short-lease", owner="alpha", ttl_s=0.05)
        # Renewal by the holder is always allowed.
        assert await leases.acquire(session, name="short-lease", owner="alpha", ttl_s=0.05)

    await asyncio.sleep(0.2)

    async with session_scope() as session:
        assert await leases.holder(session, name="short-lease") is None
        assert await leases.acquire(session, name="short-lease", owner="beta", ttl_s=60)
    async with session_scope() as session:
        assert await leases.holder(session, name="short-lease") == "beta"


async def test_release_hands_the_lease_over_without_waiting_out_the_ttl(client) -> None:  # noqa: ARG001
    async with session_scope() as session:
        assert await leases.acquire(session, name="handover", owner="alpha", ttl_s=600)
    async with session_scope() as session:
        assert await leases.release(session, name="handover", owner="alpha")
    async with session_scope() as session:
        assert await leases.acquire(session, name="handover", owner="beta", ttl_s=600)


async def test_a_lost_holder_cannot_release_the_new_holders_lease(client) -> None:  # noqa: ARG001
    """Guarded on owner: a zombie's shutdown must not evict the live holder."""
    async with session_scope() as session:
        await leases.acquire(session, name="zombie", owner="alpha", ttl_s=0.05)
    await asyncio.sleep(0.2)
    async with session_scope() as session:
        await leases.acquire(session, name="zombie", owner="beta", ttl_s=600)
    async with session_scope() as session:
        assert await leases.release(session, name="zombie", owner="alpha") is False
        assert await leases.holder(session, name="zombie") == "beta"


async def test_a_dispatcher_without_the_lease_does_no_work(make_trigger, monkeypatch) -> None:
    """A replica that lost the lease polls harmlessly; it never claims a row."""
    trigger_id = await make_trigger()
    async with session_scope() as session:
        await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="one")

    async with session_scope() as session:
        await leases.acquire(session, name=DISPATCHER_LEASE_NAME, owner="somebody-else", ttl_s=600)

    async def _explode(**_kwargs):  # pragma: no cover - the point is that it is not called
        msg = "a dispatcher without the lease must not claim"
        raise AssertionError(msg)

    monkeypatch.setattr(dispatcher, "run_once", _explode)
    assert await dispatcher.TriggerDispatcher(owner="loser").tick() == 0

    async with session_scope() as session:
        rows = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
    assert [row.state for row in rows] == [TriggerEventState.PENDING.value]
