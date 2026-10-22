"""Opt-in process-level coordination tests against an isolated PostgreSQL database.

Set LANGFLOW_TEST_DATABASE_URI to an admin database that can create test databases.
Adapters and background submissions are synthetic. Leases, claims, ledger rows,
cursor writes, process exits, and database connection failures are real.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import signal
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent, TriggerLease, TriggerSubscription
from langflow.services.database.models.user.model import User
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from tests.unit.alembic.test_migration_execution import (
    _create_pg_test_database,
    _drop_pg_test_database,
    _normalize_pg_url,
)

pytestmark = [pytest.mark.no_blockbuster, pytest.mark.integration]

TTL = 1.5
KIND = "replica.test"


def _replica_main(pipe, url: str, owner: str) -> None:
    asyncio.run(_run_replica(pipe, url, owner))


async def _run_replica(pipe, url: str, owner: str) -> None:
    from langflow.services import deps
    from langflow.services.triggers import dispatcher, lease_guard, leases, scheduler, subscriptions
    from langflow.services.triggers.listeners import adapters, supervisor
    from langflow.services.triggers.service import TriggerService

    engine = create_async_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 1})

    @asynccontextmanager
    async def scope():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
            await session.commit()

    settings = SimpleNamespace(
        trigger_lease_ttl_s=TTL,
        trigger_max_events_per_poll=25,
        trigger_dispatcher_poll_interval_s=0.05,
        trigger_replay_window_days=7,
        trigger_event_retention_days=30,
        trigger_purge_interval_s=3600,
        trigger_retry_backoff_base_s=0.05,
        trigger_retry_backoff_cap_s=1,
        listener_lease_ttl_s=TTL,
        listener_heartbeat_interval_s=0.1,
        listener_reconcile_interval_s=0.05,
        listener_backoff_base_s=0.05,
        listener_backoff_cap_s=1,
        listener_failure_threshold=3,
    )
    for module in (dispatcher, lease_guard, scheduler, supervisor, subscriptions):
        module.session_scope = scope
        if hasattr(module, "get_settings_service"):
            module.get_settings_service = lambda: SimpleNamespace(settings=settings)
    deps.get_trigger_service = TriggerService

    class IdleAdapter:
        transport = "socket"

        async def start(self, ctx):
            await ctx.stopping.wait()

        async def stop(self):
            pass

        def healthy(self):
            return True

    class JobSink:
        _frame_source_factory = object()

        async def submit(self, *, flow_id, request, user, job_id):
            async with scope() as session:
                session.add(
                    Job(
                        job_id=job_id,
                        flow_id=flow_id,
                        user_id=user.id,
                        dedupe_key=request["idempotency_key"],
                        job_metadata={"request": request},
                    )
                )
            return job_id

    deps.get_background_execution_service = JobSink
    dispatcher._ensure_frame_source = lambda: None
    adapters.register_adapter(kind=KIND, mechanism=None, factory=lambda _: IdleAdapter())
    listener = supervisor.ListenerSupervisor(holder=owner)
    dispatch = dispatcher.TriggerDispatcher(owner=owner)
    contexts = {}
    guarded = None

    async def handle(command):
        nonlocal guarded
        action = command["action"]
        if action == "reconcile":
            await listener.reconcile()
            return sorted(str(key) for key in listener.workers)
        if action == "listen":
            listener.start()
            return True
        if action == "status":
            return {"workers": sorted(str(key) for key in listener.workers), "error": listener.last_reconcile_error}
        if action == "capture":
            for connection_id, worker in listener.workers.items():
                contexts[str(connection_id)] = listener._context(worker)
            return True
        if action == "cursor":
            ctx = contexts[command["connection"]]
            await ctx.save_cursor(trigger_id=UUID(command["trigger"]), provider_state=command["state"])
            return True
        if action == "emit":
            ctx = contexts[command["connection"]]
            return await ctx.emit(trigger_id=UUID(command["trigger"]), dedupe_key=command["key"], payload={})
        if action == "tick":
            return await dispatch.tick()
        if action == "claim":
            async with scope() as session:
                rows = await dispatcher.claim_batch(session, owner=owner, limit=25, lease_ttl_s=TTL)
                return [str(row.id) for row in rows]
        if action == "renew_claim":
            async with scope() as session:
                rows = await subscriptions.claim_due(session, owner=owner, limit=25, lease_ttl_s=TTL)
                return [str(key) for key in rows]
        if action == "guard":
            async with scope() as session:
                acquired = await leases.acquire(session, name="process-test", owner=owner, ttl_s=TTL)
            if acquired:
                guarded = asyncio.create_task(
                    lease_guard.run_guarded(asyncio.sleep(30), name="process-test", owner=owner, ttl_s=TTL)
                )
            return acquired
        if action == "guard_status":
            if not guarded.done():
                return "running"
            exc = guarded.exception()
            return type(exc).__name__ if exc else "completed"
        if action == "stop_listener":
            await listener.stop()
            return True
        if action == "stop_dispatcher":
            await dispatch.stop()
            return True
        raise ValueError(action)

    pipe.send({"ready": True})
    try:
        while True:
            command = await asyncio.to_thread(pipe.recv)
            if command["action"] == "exit":
                break
            try:
                result = await handle(command)
                pipe.send({"result": result})
            except Exception as exc:
                pipe.send({"error": f"{type(exc).__name__} {exc}"})
    finally:
        if guarded is not None:
            guarded.cancel()
            await asyncio.gather(guarded, return_exceptions=True)
        await listener.stop()
        await dispatch.stop()
        await engine.dispose()
        pipe.close()


class Replica:
    def __init__(self, url: str, owner: str):
        context = multiprocessing.get_context("spawn")
        self.pipe, child = context.Pipe()
        self.process = context.Process(target=_replica_main, args=(child, url, owner))
        self.process.start()
        child.close()
        try:
            assert self.pipe.poll(30), "replica did not boot"
            assert self.pipe.recv() == {"ready": True}
        except BaseException:
            self.close()
            raise

    async def call(self, action: str, **kwargs):
        self.pipe.send({"action": action, **kwargs})
        assert await asyncio.to_thread(self.pipe.poll, 15), f"replica did not answer {action}"
        response = self.pipe.recv()
        assert "error" not in response, response.get("error")
        return response["result"]

    def close(self):
        if self.process.is_alive():
            self.pipe.send({"action": "exit"})
            self.process.join(5)
        if self.process.is_alive():
            self.process.kill()
        self.process.join(5)
        self.pipe.close()


async def _guard_settled(replica: Replica) -> str:
    deadline = asyncio.get_running_loop().time() + 5
    while (status := await replica.call("guard_status")) == "running":
        assert asyncio.get_running_loop().time() < deadline, status
        await asyncio.sleep(0.05)
    return status


@pytest.fixture
async def database():
    configured = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not configured:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI is required")
    base_url = _normalize_pg_url(configured)
    name = f"trigger_replicas_{uuid4().hex}"
    url = _create_pg_test_database(base_url, name)
    engine = create_async_engine(url, poolclass=NullPool)

    @asynccontextmanager
    async def scope():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
            await session.commit()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        async with scope() as session:
            user = User(username=f"replicas-{uuid4().hex}", password=str(uuid4()), is_active=True)
            session.add(user)
            await session.flush()
            flow = Flow(name="Replica coordination", user_id=user.id, data={"nodes": [], "edges": []})
            session.add(flow)
            await session.flush()
            yield_data = SimpleNamespace(
                url=url, base_url=base_url, name=name, scope=scope, flow_id=flow.id, user_id=user.id
            )
        yield yield_data
    finally:
        await engine.dispose()
        _drop_pg_test_database(base_url, name)


@pytest.fixture
def replicas(database):
    processes = []

    def start(owner):
        replica = Replica(database.url, owner)
        processes.append(replica)
        return replica

    yield start
    for replica in processes:
        replica.close()


async def _arm(database, *, connections=0, concurrency=1):
    async with database.scope() as session:
        rows = []
        for index in range(max(connections, 1)):
            connection = None
            if connections:
                connection = Connection(
                    provider_key="selftest",
                    name=f"replica_{index}",
                    display_name="Replica test",
                    owner_id=database.user_id,
                    status="ready",
                    allow_non_interactive=True,
                )
                session.add(connection)
                await session.flush()
            trigger = Trigger(
                name=f"replica-{index}",
                flow_id=database.flow_id,
                user_id=database.user_id,
                kind=KIND if connection else "inbound_webhook",
                state="active",
                concurrency_limit=concurrency,
                connection_id=connection.id if connection else None,
            )
            session.add(trigger)
            await session.flush()
            rows.append(trigger)
        return rows


async def test_dispatcher_processes_preserve_capacity_and_job_identity(database, replicas):
    trigger = (await _arm(database))[0]
    async with database.scope() as session:
        session.add_all(TriggerEvent(trigger_id=trigger.id, dedupe_key=str(index)) for index in range(12))
    first, second = replicas("api-a"), replicas("api-b")
    claimed = await asyncio.gather(first.call("claim"), second.call("claim"))
    assert sum(map(len, claimed)) == 1
    await asyncio.sleep(TTL + 0.1)
    # Simulate a crash after the job commits but before event accounting.
    event_id = UUID(next(batch[0] for batch in claimed if batch))
    job_id = uuid5(NAMESPACE_URL, f"langflow:trigger-event:{event_id}")
    async with database.scope() as session:
        session.add(Job(job_id=job_id, flow_id=trigger.flow_id, user_id=trigger.user_id, dedupe_key=f"trg:{event_id}"))
    await asyncio.gather(first.call("tick"), second.call("tick"))
    async with database.scope() as session:
        event = await session.get(TriggerEvent, event_id)
        assert event.state == "dispatched"
        assert event.job_id == job_id
        assert len((await session.exec(select(Job))).all()) == 1
        pending = (await session.exec(select(TriggerEvent).where(TriggerEvent.state == "pending"))).all()
        assert len(pending) == 11
        holder = (await session.exec(select(TriggerLease).where(TriggerLease.name == "trigger_dispatcher"))).one().owner
    owner, survivor = (first, second) if holder == "api-a" else (second, first)
    owner.process.kill()
    owner.process.join(5)
    burst = (await _arm(database, concurrency=50))[0]
    async with database.scope() as session:
        session.add_all(TriggerEvent(trigger_id=burst.id, dedupe_key=f"burst-{index}") for index in range(50))
    await asyncio.sleep(TTL + 0.1)
    assert await survivor.call("tick") == 25
    assert await survivor.call("tick") == 25
    async with database.scope() as session:
        events = (await session.exec(select(TriggerEvent).where(TriggerEvent.state == "dispatched"))).all()
        jobs = (await session.exec(select(Job))).all()
        assert len(events) == len(jobs) == 51
        assert {row.job_id for row in events} == {
            uuid5(NAMESPACE_URL, f"langflow:trigger-event:{row.id}") for row in events
        }


async def test_listener_processes_rebalance_and_recover_after_crash(database, replicas):
    triggers = await _arm(database, connections=4)
    first = replicas("listener-a")
    await first.call("listen")

    async def settled(*listeners, counts):
        deadline = asyncio.get_running_loop().time() + 6
        while True:
            states = await asyncio.gather(*(listener.call("status") for listener in listeners))
            if [len(state["workers"]) for state in states] == counts:
                return [set(state["workers"]) for state in states]
            assert asyncio.get_running_loop().time() < deadline, states
            await asyncio.sleep(0.05)

    await settled(first, counts=[4])
    second = replicas("listener-b")
    await second.call("listen")
    await settled(first, second, counts=[2, 2])
    first.process.kill()
    first.process.join(5)
    await settled(second, counts=[4])
    replacement = replicas("listener-c")
    await replacement.call("listen")
    held = await settled(second, replacement, counts=[2, 2])
    assert held[0].isdisjoint(held[1])
    assert held[0] | held[1] == {str(row.connection_id) for row in triggers}
    await second.call("stop_listener")
    await settled(replacement, counts=[4])


async def test_stale_listener_cannot_rewind_cursor_and_duplicate_delivery_is_collapsed(database, replicas):
    trigger = (await _arm(database, connections=1))[0]
    first, second = replicas("listener-old"), replicas("listener-new")
    await first.call("reconcile")
    await first.call("capture")
    await asyncio.sleep(TTL + 0.1)
    await second.call("reconcile")
    await second.call("capture")
    args = {"connection": str(trigger.connection_id), "trigger": str(trigger.id)}
    await second.call("cursor", **args, state={"cursor": "new"})
    # A unique stale delivery proves fencing independently of deduplication.
    # Child-process exceptions cross the pipe as explicit error records.
    with pytest.raises(AssertionError, match="ListenerDeliveryRejectedError"):
        await first.call("emit", **args, key="stale-only-event")
    await first.call("cursor", **args, state={"cursor": "old"})
    assert await second.call("emit", **args, key="same-event") is True
    assert await second.call("emit", **args, key="same-event") is False
    async with database.scope() as session:
        assert (await session.get(Trigger, trigger.id)).provider_state == {"cursor": "new"}
        assert len((await session.exec(select(TriggerEvent))).all()) == 1


async def test_stale_listener_generation_cannot_rewind_cursor(database, replicas):
    trigger = (await _arm(database, connections=1))[0]
    first, second = replicas("listener-same"), replicas("listener-same")
    await first.call("reconcile")
    await first.call("capture")
    # Releasing and reclaiming starts a new generation even with the same
    # holder identity. Keep the captured old context to simulate a late callback.
    await first.call("stop_listener")
    await second.call("reconcile")
    await second.call("capture")
    args = {"connection": str(trigger.connection_id), "trigger": str(trigger.id)}
    await second.call("cursor", **args, state={"cursor": "new"})
    with pytest.raises(AssertionError, match="ListenerDeliveryRejectedError"):
        await first.call("emit", **args, key="stale-generation-event")
    await first.call("cursor", **args, state={"cursor": "old"})
    async with database.scope() as session:
        assert (await session.get(Trigger, trigger.id)).provider_state == {"cursor": "new"}


async def test_subscription_claims_have_one_owner_and_expire_after_process_death(database, replicas):
    trigger = (await _arm(database))[0]
    async with database.scope() as session:
        subscription = TriggerSubscription(
            trigger_id=trigger.id,
            provider="selftest",
            provider_subscription_id="test-watch",
            state="active",
            renew_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        session.add(subscription)
        await session.flush()
        subscription_id = str(subscription.id)
    first, second = replicas("renew-a"), replicas("renew-b")
    claims = await asyncio.gather(first.call("renew_claim"), second.call("renew_claim"))
    assert sorted(map(len, claims)) == [0, 1]
    winner, survivor = (first, second) if claims[0] else (second, first)
    winner.process.kill()
    winner.process.join(5)
    await asyncio.sleep(TTL + 0.1)
    assert await survivor.call("renew_claim") == [subscription_id]


async def test_heartbeat_blocks_takeover_and_database_outage_cancels_guarded_work(database, replicas):
    first, second = replicas("guard-a"), replicas("guard-b")
    assert await first.call("guard") is True
    await asyncio.sleep(TTL * 1.5)
    assert await second.call("guard") is False
    admin = create_engine(database.base_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f"ALTER DATABASE {database.name} ALLOW_CONNECTIONS false"))
            connection.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name"),
                {"name": database.name},
            )
        assert await _guard_settled(first) == "LeaseLostError"
    finally:
        with admin.connect() as connection:
            connection.execute(text(f"ALTER DATABASE {database.name} ALLOW_CONNECTIONS true"))
        admin.dispose()
    await asyncio.sleep(TTL)
    assert await second.call("guard") is True


@pytest.mark.skipif(os.name != "posix", reason="requires process stop and continue signals")
async def test_stalled_owner_is_fenced_after_takeover(replicas):
    first, second = replicas("stalled-owner"), replicas("replacement-owner")
    assert await first.call("guard") is True
    os.kill(first.process.pid, signal.SIGSTOP)
    try:
        await asyncio.sleep(TTL + 0.2)
        assert await second.call("guard") is True
    finally:
        os.kill(first.process.pid, signal.SIGCONT)
    assert await _guard_settled(first) == "LeaseLostError"
