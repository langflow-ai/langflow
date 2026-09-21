"""What the supervisor promises: hold, drop, back off, and never run twice.

Every test drives the real reconcile against the real tables. The adapter is
fake - TRG-3 ships no provider source - but everything around it is production
code: the lease, the ledger write, the trigger state transitions, the backoff
accounting.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.trigger.schemas import TriggerState
from langflow.services.deps import session_scope
from langflow.services.triggers.listeners import connection_leases
from langflow.services.triggers.listeners.adapters import (
    ListenerContext,
    ListenerTrigger,
    register_adapter,
    unregister_adapter,
)
from langflow.services.triggers.listeners.supervisor import ListenerSupervisor
from lfx.integrations.errors import AuthExpiredError
from sqlmodel import col, select

pytestmark = pytest.mark.no_blockbuster

TEST_KIND = "test_listener_source"


class RecordingAdapter:
    """A socket-shaped adapter: it holds until cancelled, and can be told to fail."""

    transport = "socket"

    def __init__(self, *, fail_with: Exception | None = None, emit_on_start: bool = False) -> None:
        self.fail_with = fail_with
        self.emit_on_start = emit_on_start
        self.started = asyncio.Event()
        self.stopped = False
        self.start_count = 0

    async def start(self, ctx: ListenerContext) -> None:
        self.start_count += 1
        self.started.set()
        if self.emit_on_start:
            for trigger in ctx.triggers:
                await ctx.emit(
                    trigger_id=trigger.id,
                    dedupe_key=f"test:{self.start_count}",
                    payload={"start": self.start_count},
                )
        if self.fail_with is not None:
            raise self.fail_with
        await ctx.stopping.wait()

    async def stop(self) -> None:
        self.stopped = True

    def healthy(self) -> bool:
        return True


@pytest.fixture
def adapter_registry():
    """Register a controllable adapter for TEST_KIND and clean up afterwards.

    The registry is process-global by design (a bundle registers its adapter at
    import time), so a test that leaves an entry behind poisons the next one.
    """
    state: dict[str, RecordingAdapter] = {}

    def install(adapter: RecordingAdapter) -> RecordingAdapter:
        state["adapter"] = adapter
        return adapter

    def factory(_trigger: ListenerTrigger):
        return state["adapter"]

    register_adapter(kind=TEST_KIND, mechanism=None, factory=factory)
    try:
        yield install
    finally:
        unregister_adapter(kind=TEST_KIND, mechanism=None)


@pytest.fixture
def make_connection(trigger_owner):
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


async def _state(trigger_id) -> tuple[str, str | None]:
    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        return row.state, row.last_error


async def test_an_armed_trigger_is_held_and_a_paused_one_is_released(
    make_connection, make_trigger, adapter_registry
) -> None:
    adapter = adapter_registry(RecordingAdapter())
    connection_id = await make_connection()
    trigger_id = await make_trigger(kind=TEST_KIND, connection_id=connection_id)

    supervisor = ListenerSupervisor(holder="replica-a")
    await supervisor.reconcile()
    await asyncio.wait_for(adapter.started.wait(), timeout=5)

    assert connection_id in supervisor.workers
    async with session_scope() as session:
        assert await connection_leases.current_holder(session, connection_id=connection_id, ttl_s=300) == "replica-a"

    # The owner pauses the trigger: the connection is no longer wanted.
    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        row.state = TriggerState.PAUSED.value
        session.add(row)

    await supervisor.reconcile()

    assert connection_id not in supervisor.workers
    assert adapter.stopped is True
    async with session_scope() as session:
        assert await connection_leases.current_holder(session, connection_id=connection_id, ttl_s=300) is None


async def test_only_one_replica_holds_a_connection(make_connection, make_trigger, adapter_registry) -> None:
    adapter_registry(RecordingAdapter())
    connection_id = await make_connection()
    await make_trigger(kind=TEST_KIND, connection_id=connection_id)

    first = ListenerSupervisor(holder="replica-a")
    second = ListenerSupervisor(holder="replica-b")
    await first.reconcile()
    await second.reconcile()

    try:
        assert list(first.workers) == [connection_id]
        assert list(second.workers) == []
    finally:
        await first.stop()
        await second.stop()


async def test_losing_the_lease_cancels_the_adapter(make_connection, make_trigger, adapter_registry) -> None:
    """The one state this design must not have: an adapter running without a lease."""
    adapter = adapter_registry(RecordingAdapter())
    connection_id = await make_connection()
    await make_trigger(kind=TEST_KIND, connection_id=connection_id)

    supervisor = ListenerSupervisor(holder="replica-a")
    await supervisor.reconcile()
    await asyncio.wait_for(adapter.started.wait(), timeout=5)

    # Another replica steals the lease (as it would after this one stalled).
    async with session_scope() as session:
        await connection_leases.release(session, connection_id=connection_id, holder="replica-a")
        await connection_leases.claim(session, connection_id=connection_id, holder="replica-b", ttl_s=300)

    # Force the heartbeat to be due so the next pass tries to renew.
    supervisor.workers[connection_id].last_renewed_at = supervisor.workers[connection_id].last_renewed_at.replace(
        year=2020
    )
    await supervisor.reconcile()

    assert connection_id not in supervisor.workers
    assert supervisor.last_renew_failure_at is not None
    async with session_scope() as session:
        assert await connection_leases.current_holder(session, connection_id=connection_id, ttl_s=300) == "replica-b"


async def test_a_revoked_connection_moves_its_triggers_to_needs_reconnect(
    make_connection, make_trigger, adapter_registry
) -> None:
    adapter_registry(RecordingAdapter())
    connection_id = await make_connection(status="revoked")
    trigger_id = await make_trigger(kind=TEST_KIND, connection_id=connection_id)

    supervisor = ListenerSupervisor(holder="replica-a")
    await supervisor.reconcile()

    assert supervisor.workers == {}
    state, last_error = await _state(trigger_id)
    assert state == TriggerState.NEEDS_RECONNECT.value
    assert "econnect" in (last_error or "")


async def test_an_auth_failure_stops_retrying_and_asks_for_a_reconnect(
    make_connection, make_trigger, adapter_registry
) -> None:
    """A revoked token is the one failure backoff can never fix."""
    adapter = adapter_registry(RecordingAdapter(fail_with=AuthExpiredError(provider="selftest")))
    connection_id = await make_connection()
    trigger_id = await make_trigger(kind=TEST_KIND, connection_id=connection_id)

    supervisor = ListenerSupervisor(holder="replica-a")
    await supervisor.reconcile()
    await asyncio.wait_for(adapter.started.wait(), timeout=5)
    # Let the worker task run to its failure handler.
    for _ in range(50):
        if connection_id not in supervisor.workers:
            break
        await asyncio.sleep(0.05)

    assert connection_id not in supervisor.workers
    state, _ = await _state(trigger_id)
    assert state == TriggerState.NEEDS_RECONNECT.value
    async with session_scope() as session:
        assert await connection_leases.current_holder(session, connection_id=connection_id, ttl_s=300) is None


async def test_persistent_failures_back_off_and_surface_the_error_then_a_success_clears_it(
    make_connection, make_trigger, adapter_registry, monkeypatch
) -> None:
    """The LE-2479 QA case: five consecutive failures, then recovery."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "listener_backoff_base_s", 0.01)
    monkeypatch.setattr(settings, "listener_backoff_cap_s", 0.02)

    adapter = adapter_registry(RecordingAdapter(fail_with=RuntimeError("provider said no")))
    connection_id = await make_connection()
    trigger_id = await make_trigger(kind=TEST_KIND, connection_id=connection_id)

    supervisor = ListenerSupervisor(holder="replica-a")
    await supervisor.reconcile()
    worker = supervisor.workers[connection_id]

    # Drive five failing attempts the way the reconcile loop would.
    for _ in range(5):
        if worker.task is not None:
            await asyncio.gather(worker.task, return_exceptions=True)
        worker.next_attempt_at = None
        supervisor._spawn(worker)
    await asyncio.gather(worker.task, return_exceptions=True)

    assert worker.consecutive_failures >= 5
    assert worker.resting() is True, "a failed connection must rest before the next attempt"
    _state_value, last_error = await _state(trigger_id)
    assert "could not hold this connection" in (last_error or "")
    # The trigger stays armed: a flapping provider is not an owner misconfiguration.
    assert _state_value == TriggerState.ACTIVE.value

    # Now it recovers: one delivered event clears the banner.
    adapter.fail_with = None
    adapter.emit_on_start = True
    worker.next_attempt_at = None
    supervisor._spawn(worker)
    for _ in range(50):
        _state_value, last_error = await _state(trigger_id)
        if last_error is None:
            break
        await asyncio.sleep(0.05)

    await supervisor.stop()
    assert last_error is None
    assert worker.consecutive_failures == 0


async def test_one_event_per_dedupe_key_however_many_replicas_emit_it(
    make_connection, make_trigger, adapter_registry
) -> None:
    """Bounded overlap during handover must not produce two runs."""
    adapter = adapter_registry(RecordingAdapter(emit_on_start=True))
    connection_id = await make_connection()
    trigger_id = await make_trigger(kind=TEST_KIND, connection_id=connection_id)

    supervisor = ListenerSupervisor(holder="replica-a")
    await supervisor.reconcile()
    worker = supervisor.workers[connection_id]
    ctx = supervisor._context(worker)

    created = await asyncio.gather(
        *[ctx.emit(trigger_id=trigger_id, dedupe_key="overlap:1", payload={"n": index}) for index in range(5)]
    )
    await supervisor.stop()

    assert sum(created) == 1, "the ledger's unique index must collapse the duplicates"
    async with session_scope() as session:
        rows = (
            await session.exec(
                select(TriggerEvent).where(
                    TriggerEvent.trigger_id == trigger_id,
                    col(TriggerEvent.dedupe_key) == "overlap:1",
                )
            )
        ).all()
    assert len(rows) == 1
    assert adapter.start_count >= 1


async def test_a_schedule_trigger_is_never_held_by_a_listener(make_connection, make_trigger) -> None:
    """The listener walks past every trigger kind no adapter claims."""
    connection_id = await make_connection()
    await make_trigger(kind="schedule", connection_id=connection_id, config={"cron": "0 8 * * *"})

    supervisor = ListenerSupervisor(holder="replica-a")
    await supervisor.reconcile()

    assert supervisor.workers == {}
    async with session_scope() as session:
        assert await connection_leases.current_holder(session, connection_id=connection_id, ttl_s=300) is None


async def test_stop_releases_every_lease_and_stops_every_adapter(
    make_connection, make_trigger, adapter_registry
) -> None:
    adapter = adapter_registry(RecordingAdapter())
    connection_id = await make_connection()
    await make_trigger(kind=TEST_KIND, connection_id=connection_id)

    supervisor = ListenerSupervisor(holder="replica-a")
    supervisor.start()
    for _ in range(60):
        if connection_id in supervisor.workers:
            break
        await asyncio.sleep(0.1)
    assert connection_id in supervisor.workers

    await supervisor.stop()

    assert supervisor.workers == {}
    assert adapter.stopped is True
    async with session_scope() as session:
        assert await connection_leases.held_by(session, holder="replica-a", ttl_s=300) == set()
