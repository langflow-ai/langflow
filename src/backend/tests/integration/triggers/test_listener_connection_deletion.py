"""Real PostgreSQL deletion must serialize with listener delivery and cursor writes."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.connection.service import DatabaseConnectionResolverService
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent, TriggerListenerLease
from langflow.services.database.models.user.model import User
from langflow.services.triggers.constants import MECHANISM_SLACK_SOCKET_MODE, SLACK_PROVIDER_STATE_APP_ID
from langflow.services.triggers.listeners import adapters, connection_leases, supervisor
from langflow.services.triggers.listeners.adapters import ListenerDeliveryRejectedError
from sqlalchemy import text
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


@pytest.fixture
async def listener_database():
    configured = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not configured:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI is required")
    base_url = _normalize_pg_url(configured)
    name = f"listener_delete_{uuid4().hex}"
    engine = create_async_engine(_create_pg_test_database(base_url, name), poolclass=NullPool)

    @asynccontextmanager
    async def scope():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
            await session.commit()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        yield SimpleNamespace(scope=scope)
    finally:
        await engine.dispose()
        _drop_pg_test_database(base_url, name)


@pytest.mark.parametrize(
    ("operation", "deleted_connection"), [("emit", "source"), ("cursor", "source"), ("emit", "fanout_target")]
)
async def test_connection_deletion_serializes_with_listener_writes(
    listener_database, monkeypatch, operation, deleted_connection
):
    database = listener_database
    fanout = deleted_connection == "fanout_target"
    monkeypatch.setattr(adapters, "_REGISTRY", {})
    adapters.register_adapter(kind="slack.message", mechanism=MECHANISM_SLACK_SOCKET_MODE, factory=lambda _: None)
    monkeypatch.setattr(
        supervisor,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(listener_lease_ttl_s=300, listener_failure_threshold=3)),
    )
    async with database.scope() as session:
        user = User(username=f"listener-delete-{uuid4().hex}", password=str(uuid4()), is_active=True)
        session.add(user)
        await session.flush()
        flow = Flow(name="Listener deletion", user_id=user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        connections = []
        triggers = []
        for index in range(2 if fanout else 1):
            connection = Connection(
                provider_key="slack",
                name=f"socket_{index}",
                display_name="Test socket",
                owner_id=user.id,
                status="ready",
                allow_non_interactive=True,
                executing_identity={"identity": "bot"},
            )
            session.add(connection)
            await session.flush()
            trigger = Trigger(
                flow_id=flow.id,
                user_id=user.id,
                name=f"Source {index}",
                kind="slack.message",
                provider="slack",
                state="active",
                connection_id=connection.id,
                config={"mechanism_id": MECHANISM_SLACK_SOCKET_MODE},
                provider_state={SLACK_PROVIDER_STATE_APP_ID: "test-app"},
            )
            session.add(trigger)
            await session.flush()
            connections.append(connection)
            triggers.append(trigger)
        generation = await connection_leases.claim_generation(
            session, connection_id=connections[0].id, holder="listener-delete-test", ttl_s=300
        )
    source, target = triggers[0], triggers[-1]
    worker = supervisor.ConnectionWorker(
        connection_id=connections[0].id,
        triggers=[supervisor._snapshot(source)],
        adapter=SimpleNamespace(),
        stopping=asyncio.Event(),
        lease_generation=generation,
    )
    context = supervisor.ListenerSupervisor(holder="listener-delete-test")._context(worker)
    started = asyncio.Event()
    backend_pid = None

    @asynccontextmanager
    async def delivery_scope():
        nonlocal backend_pid
        async with database.scope() as session:
            backend_pid = (await session.exec(text("SELECT pg_backend_pid()"))).scalar_one()
            started.set()
            yield session

    monkeypatch.setattr(supervisor, "session_scope", delivery_scope)

    async def deliver():
        if operation == "cursor":
            return await context.save_cursor(trigger_id=target.id, provider_state={"cursor": "stale"})
        return await context.emit(
            trigger_id=target.id,
            dedupe_key="delete-race:fresh",
            payload={},
            expected_config=target.config,
            expected_kind=target.kind,
        )

    delivery = None
    try:
        async with database.scope() as session:
            connection = await session.get(Connection, connections[-1].id, with_for_update=True)
            delivery = asyncio.create_task(deliver())
            await asyncio.wait_for(started.wait(), timeout=5)
            # Wait for the real delivery SQL to block on this connection. No
            # production lock helper is mocked or manually reproduced here.
            async with asyncio.timeout(5):
                while True:
                    async with database.scope() as observer:
                        waiting = (
                            await observer.exec(
                                text(
                                    "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :pid"
                                ).bindparams(pid=backend_pid)
                            )
                        ).scalar_one()
                    if waiting:
                        break
                    await asyncio.sleep(0.01)
            await asyncio.wait_for(DatabaseConnectionResolverService().delete(session, connection), timeout=10)
        result = (await asyncio.wait_for(asyncio.gather(delivery, return_exceptions=True), timeout=5))[0]
        if operation == "emit":
            assert isinstance(result, ListenerDeliveryRejectedError), result
        else:
            assert result is None
        assert context.stopping.is_set() is (not fanout)
        async with database.scope() as session:
            assert await session.get(Connection, connections[-1].id) is None
            assert (await session.get(Trigger, target.id)).connection_id is None
            assert (await session.get(Trigger, target.id)).provider_state == {SLACK_PROVIDER_STATE_APP_ID: "test-app"}
            assert not (await session.exec(select(TriggerEvent))).all()
            if not fanout:
                assert await session.get(TriggerListenerLease, connections[0].id) is None
    finally:
        if delivery is not None:
            delivery.cancel()
            await asyncio.gather(delivery, return_exceptions=True)
