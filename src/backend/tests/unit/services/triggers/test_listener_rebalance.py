"""Adding a replica to a loaded listener deployment has to move connections.

The lease alone cannot do it. It is invisible until it is held, so a replica
that has just started is invisible to the replica already holding everything,
and nothing moves - which is the LE-2479 finding: three shipped texts tell
operators to scale out for exactly the case that did nothing. These tests drive
two and three real supervisors against the real tables and assert the load
actually moves.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import TriggerLease
from langflow.services.deps import session_scope
from langflow.services.triggers.listeners import connection_leases, replicas
from langflow.services.triggers.listeners.adapters import (
    ListenerContext,
    ListenerTrigger,
    register_adapter,
    unregister_adapter,
)
from langflow.services.triggers.listeners.supervisor import ListenerSupervisor
from sqlmodel import col, select

pytestmark = pytest.mark.no_blockbuster

TEST_KIND = "test_rebalance_source"


class IdleAdapter:
    """Holds until cancelled. Rebalancing is about leases, not about traffic."""

    transport = "socket"

    def __init__(self) -> None:
        self.stopped = False

    async def start(self, ctx: ListenerContext) -> None:
        await ctx.stopping.wait()

    async def stop(self) -> None:
        self.stopped = True

    def healthy(self) -> bool:
        return True


@pytest.fixture
def adapter_registry():
    def factory(_trigger: ListenerTrigger):
        return IdleAdapter()

    register_adapter(kind=TEST_KIND, mechanism=None, factory=factory)
    try:
        yield
    finally:
        unregister_adapter(kind=TEST_KIND, mechanism=None)


@pytest.fixture
def make_connection(trigger_owner):
    async def _make():
        async with session_scope() as session:
            row = Connection(
                provider_key="selftest",
                name=f"conn_{uuid4().hex[:8]}",
                display_name="Self test",
                ownership_mode="user",
                owner_id=trigger_owner,
                status="ready",
                allow_non_interactive=True,
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return row.id

    return _make


@pytest.fixture
def armed_connections(make_connection, make_trigger, adapter_registry):  # noqa: ARG001
    async def _arm(count: int) -> list:
        ids = []
        for _ in range(count):
            connection_id = await make_connection()
            await make_trigger(kind=TEST_KIND, connection_id=connection_id)
            ids.append(connection_id)
        return ids

    return _arm


async def _settle(supervisors: list[ListenerSupervisor], *, passes: int) -> None:
    """Reconcile every replica in turn, the way the real loops interleave."""
    for _ in range(passes):
        for supervisor in supervisors:
            await supervisor.reconcile()
        # Hand-backs pause the releasing replica for two reconcile intervals, so
        # real time has to advance for it to stop refusing what it gave away.
        await asyncio.sleep(0)


def test_fair_share_rounds_up_and_a_lone_replica_keeps_everything() -> None:
    assert replicas.fair_share(total=31, replicas=1) == 31
    # Rounded up, so three shares cover thirty-one connections instead of
    # leaving one that no replica is allowed to hold.
    assert replicas.fair_share(total=31, replicas=3) == 11
    assert replicas.fair_share(total=2, replicas=5) == 1
    assert replicas.fair_share(total=0, replicas=3) == 0
    # A replica that cannot even see itself holds on to what it has: handing a
    # connection back to nobody is strictly worse than keeping it.
    assert replicas.fair_share(total=9, replicas=0) == 9


async def test_a_replica_added_to_a_loaded_deployment_takes_its_share(armed_connections) -> None:
    """The finding itself: replica two used to sit at zero connections forever."""
    connection_ids = await armed_connections(6)

    first = ListenerSupervisor(holder="replica-a")
    await first.reconcile()
    assert len(first.workers) == len(connection_ids), "the lone replica should hold everything"

    second = ListenerSupervisor(holder="replica-b")
    try:
        # One pass for `second` to announce itself, one for `first` to notice
        # the peer and hand back, one for `second` to claim what was freed.
        for _ in range(4):
            await second.reconcile()
            await first.reconcile()

        assert len(first.workers) == 3
        assert len(second.workers) == 3
        assert set(first.workers) | set(second.workers) == set(connection_ids)
        assert not set(first.workers) & set(second.workers), "a connection is held by exactly one replica"
    finally:
        await first.stop()
        await second.stop()


async def test_a_third_replica_splits_the_load_again(armed_connections) -> None:
    connection_ids = await armed_connections(6)

    first = ListenerSupervisor(holder="replica-a")
    second = ListenerSupervisor(holder="replica-b")
    third = ListenerSupervisor(holder="replica-c")
    try:
        for _ in range(4):
            await first.reconcile()
            await second.reconcile()
        assert (len(first.workers), len(second.workers)) == (3, 3)

        for _ in range(6):
            await third.reconcile()
            await first.reconcile()
            await second.reconcile()

        held = [len(first.workers), len(second.workers), len(third.workers)]
        assert sum(held) == len(connection_ids)
        assert max(held) <= 2, f"no replica should exceed its share of two: {held}"
    finally:
        for supervisor in (first, second, third):
            await supervisor.stop()


async def test_a_lone_replica_never_hands_anything_back(armed_connections) -> None:
    """The single-replica case must be untouched by all of this."""
    connection_ids = await armed_connections(4)

    supervisor = ListenerSupervisor(holder="replica-a")
    try:
        for _ in range(3):
            await supervisor.reconcile()
        assert set(supervisor.workers) == set(connection_ids)
        assert supervisor.live_replicas == 1
        assert supervisor.fair_share == len(connection_ids)
    finally:
        await supervisor.stop()


async def test_a_departed_replica_stops_counting_and_its_share_returns(armed_connections) -> None:
    connection_ids = await armed_connections(4)

    first = ListenerSupervisor(holder="replica-a")
    second = ListenerSupervisor(holder="replica-b")
    for _ in range(4):
        await first.reconcile()
        await second.reconcile()
    assert len(second.workers) == 2

    # Replica B leaves cleanly: presence row gone, leases released.
    await second.stop()
    async with session_scope() as session:
        assert await replicas.live_replicas(session) == 1

    # Fast-forward through the pause this replica set when it handed those two
    # away. Sleeping it out would be the same assertion, ten seconds slower.
    first._handed_back.clear()

    try:
        for _ in range(3):
            await first.reconcile()
        assert set(first.workers) == set(connection_ids)
    finally:
        await first.stop()


async def test_stopping_withdraws_the_presence_row(armed_connections) -> None:
    await armed_connections(1)
    supervisor = ListenerSupervisor(holder="replica-a")
    await supervisor.reconcile()

    async with session_scope() as session:
        assert await replicas.live_replicas(session) == 1

    await supervisor.stop()

    async with session_scope() as session:
        assert await replicas.live_replicas(session) == 0


async def test_a_handed_back_connection_is_not_immediately_reclaimed(armed_connections) -> None:
    """Otherwise the replica that released it wins the race back every time."""
    connection_ids = await armed_connections(2)

    first = ListenerSupervisor(holder="replica-a")
    second = ListenerSupervisor(holder="replica-b")
    try:
        await first.reconcile()
        assert len(first.workers) == 2

        await second.reconcile()  # announce, so `first` can see a peer
        await first.reconcile()  # hand one back
        assert len(first.workers) == 1
        released = (set(connection_ids) - set(first.workers)).pop()

        # Nobody holds it yet, and `first` refuses to take it back.
        async with session_scope() as session:
            assert await connection_leases.current_holder(session, connection_id=released, ttl_s=300) is None
        await first.reconcile()
        assert released not in first.workers
    finally:
        await first.stop()
        await second.stop()


async def test_a_hard_killed_replica_stops_counting_and_is_eventually_reaped(client) -> None:  # noqa: ARG001
    """No SIGTERM means no withdraw, so presence has to expire and then be swept."""
    async with session_scope() as session:
        await replicas.announce(session, holder="replica-gone", ttl_s=-1)

    async with session_scope() as session:
        # Already expired, so it is not counted - a dead replica must not shrink
        # a live one's share.
        assert await replicas.live_replicas(session) == 0
        # ...and not yet old enough to delete, so a clock skew cannot reap a row
        # that is about to be renewed.
        assert await replicas.live_replicas(session, reap_after_s=3600) == 0

    async with session_scope() as session:
        assert await replicas.live_replicas(session, reap_after_s=0) == 0
    async with session_scope() as session:
        rows = (
            await session.exec(select(TriggerLease).where(col(TriggerLease.name).like(f"{replicas.PRESENCE_PREFIX}%")))
        ).all()
    assert rows == []
