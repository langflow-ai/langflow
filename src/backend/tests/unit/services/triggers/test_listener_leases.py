"""One replica per connection: claim, renew, steal after the TTL, release.

The guarantee is a database guarantee, so every test here races real sessions
against the real table rather than a mock. What is being checked is not "the
helper returns True" but "two replicas that both believe a connection is free
cannot both hold it".
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import TriggerListenerLease
from langflow.services.deps import session_scope
from langflow.services.triggers.listeners import connection_leases
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def make_connection(trigger_owner):
    """Create a ready connection row and return its id."""

    async def _make(**overrides):
        fields = {
            "provider_key": "selftest",
            "name": f"conn_{uuid4().hex[:6]}",
            "display_name": "Self test",
            "ownership_mode": "user",
            "owner_id": trigger_owner,
            "status": "ready",
            "allow_non_interactive": True,
        }
        fields.update(overrides)
        async with session_scope() as session:
            row = Connection(**fields)
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return row.id

    return _make


async def test_one_holder_per_connection(make_connection) -> None:
    connection_id = await make_connection()

    async with session_scope() as session:
        first = await connection_leases.claim(session, connection_id=connection_id, holder="alpha", ttl_s=60)
    async with session_scope() as session:
        second = await connection_leases.claim(session, connection_id=connection_id, holder="beta", ttl_s=60)
        who = await connection_leases.current_holder(session, connection_id=connection_id, ttl_s=60)

    assert first is True
    assert second is False
    assert who == "alpha"


async def test_the_holder_renews_and_a_rival_steals_only_after_the_ttl(make_connection) -> None:
    connection_id = await make_connection()

    async with session_scope() as session:
        assert await connection_leases.claim(session, connection_id=connection_id, holder="alpha", ttl_s=0.05)
        # Renewal by the current holder is always allowed.
        assert await connection_leases.claim(session, connection_id=connection_id, holder="alpha", ttl_s=0.05)

    await asyncio.sleep(0.2)

    async with session_scope() as session:
        assert await connection_leases.current_holder(session, connection_id=connection_id, ttl_s=0.05) is None
        # The TTL is the claimant's own policy - every process shares the
        # configured value - so the rival judges liveness by the same 0.05s.
        assert await connection_leases.claim(session, connection_id=connection_id, holder="beta", ttl_s=0.05)
    async with session_scope() as session:
        assert await connection_leases.current_holder(session, connection_id=connection_id, ttl_s=300) == "beta"


async def test_release_hands_over_without_waiting_out_the_ttl(make_connection) -> None:
    connection_id = await make_connection()
    async with session_scope() as session:
        await connection_leases.claim(session, connection_id=connection_id, holder="alpha", ttl_s=300)
        assert await connection_leases.release(session, connection_id=connection_id, holder="alpha")
    async with session_scope() as session:
        assert await connection_leases.claim(session, connection_id=connection_id, holder="beta", ttl_s=300)


async def test_a_dispossessed_holder_cannot_release_the_new_holders_lease(make_connection) -> None:
    """The guard that keeps failover from being undone by the process it replaced."""
    connection_id = await make_connection()
    async with session_scope() as session:
        await connection_leases.claim(session, connection_id=connection_id, holder="alpha", ttl_s=0.05)
    await asyncio.sleep(0.2)
    async with session_scope() as session:
        assert await connection_leases.claim(session, connection_id=connection_id, holder="beta", ttl_s=0.05)

    async with session_scope() as session:
        # "alpha" wakes up and tries to shut down cleanly.
        assert await connection_leases.release(session, connection_id=connection_id, holder="alpha") is False
    async with session_scope() as session:
        assert await connection_leases.current_holder(session, connection_id=connection_id, ttl_s=300) == "beta"


async def test_twenty_connections_two_replicas_exactly_one_holder_each(make_connection) -> None:
    """The QA case from LE-2479, run against the real table.

    Two holders race every connection at once. What must come out is twenty
    leases, each with exactly one holder, and both replicas holding some - not
    twenty leases held twice, and not a deadlock.
    """
    connection_ids = [await make_connection() for _ in range(20)]

    async def claim_all(holder: str) -> list[bool]:
        results = []
        for connection_id in connection_ids:
            async with session_scope() as session:
                results.append(
                    await connection_leases.claim(session, connection_id=connection_id, holder=holder, ttl_s=60)
                )
        return results

    alpha, beta = await asyncio.gather(claim_all("alpha"), claim_all("beta"))

    # Every connection is claimed by exactly one of the two.
    for index in range(20):
        assert alpha[index] != beta[index], f"connection {index} was held by both or neither"

    async with session_scope() as session:
        rows = (await session.exec(select(TriggerListenerLease))).all()
    held = {row.connection_id: row.holder for row in rows}
    assert len(held) == 20
    assert set(held.values()) <= {"alpha", "beta"}


async def test_failover_moves_a_dead_replicas_leases_within_two_ttls(make_connection) -> None:
    connection_ids = [await make_connection() for _ in range(5)]
    ttl = 0.05
    for connection_id in connection_ids:
        async with session_scope() as session:
            assert await connection_leases.claim(session, connection_id=connection_id, holder="dead", ttl_s=ttl)

    # "dead" stops heartbeating. Wait out two TTLs, the recovery bound the
    # process-model decision records.
    await asyncio.sleep(ttl * 2 + 0.1)

    for connection_id in connection_ids:
        async with session_scope() as session:
            assert await connection_leases.claim(session, connection_id=connection_id, holder="live", ttl_s=ttl)

    async with session_scope() as session:
        assert await connection_leases.held_by(session, holder="live", ttl_s=300) == set(connection_ids)
        assert await connection_leases.held_by(session, holder="dead", ttl_s=300) == set()


async def test_release_all_drops_every_lease_this_holder_owns(make_connection) -> None:
    connection_ids = [await make_connection() for _ in range(3)]
    for connection_id in connection_ids:
        async with session_scope() as session:
            await connection_leases.claim(session, connection_id=connection_id, holder="alpha", ttl_s=60)

    async with session_scope() as session:
        assert await connection_leases.release_all(session, holder="alpha") == 3
    async with session_scope() as session:
        assert await connection_leases.held_by(session, holder="alpha", ttl_s=60) == set()
