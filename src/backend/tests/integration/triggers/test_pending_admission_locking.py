"""Pending provider reservations keep real connection/trigger FK lock order."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.connection.service import DatabaseConnectionResolverService
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.database.models.trigger.schemas import TriggerBulkRequest
from langflow.services.database.models.user.model import User
from langflow.services.triggers import operator, source_arming, source_subscription
from langflow.services.triggers.ingress.verifiers import IngressRejected
from langflow.services.triggers.providers import registry
from langflow.services.triggers.service import TriggerService
from sqlalchemy import text
from sqlmodel import select

from tests.integration.triggers.test_listener_connection_deletion import listener_database  # noqa: F401

pytestmark = [pytest.mark.no_blockbuster, pytest.mark.integration]


@pytest.fixture
def pending_provider(monkeypatch, request):
    provider_id = request.param
    identity = "service" if provider_id == "github" else "user_delegated"
    prepared = []

    async def prepare(session, trigger):
        # GitHub and GitLab persist this same pre-I/O reservation. Exercise the
        # shared admission contract and both real FKs without a provider wheel.
        prepared.append(trigger.id)
        reservation_id = uuid4()
        session.add(
            TriggerSubscription(
                id=reservation_id,
                trigger_id=trigger.id,
                connection_id=trigger.connection_id,
                provider=provider_id,
                provider_subscription_id=f"pending:{reservation_id}",
                state="pending",
            )
        )
        await session.flush()

    async def origin(_session, _connection_id):
        return "https://langflow.example"

    async def allow_policy(*_args, **_kwargs):
        return None

    def verify(*_args, **_kwargs):
        msg = "test_no_ingress"
        raise IngressRejected(msg)

    provider = registry.TriggerProvider(
        provider_id=provider_id,
        bundle=provider_id,
        normalize_config=lambda _kind, raw: raw,
        kinds=(
            registry.TriggerKind(
                kind=f"{provider_id}.issue",
                component="PendingIssueComponent",
                display_name="Pending issue",
                config_fields=("connection", "delivery_mode"),
                push_mechanism=f"{provider_id}.webhook",
                identity=identity,
            ),
        ),
        prepare=prepare,
        verify=verify,
    )
    monkeypatch.setattr(registry, "all_providers", lambda: (provider,))
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    monkeypatch.setattr(source_subscription, "configured_ingress_origin", origin)
    monkeypatch.setattr("langflow.services.connection.service.enforce_integration_policy_for_provider", allow_policy)
    settings = source_arming.get_settings_service().settings
    monkeypatch.setattr(settings, "trigger_ingress_enabled", True)
    return provider_id, identity, prepared


@pytest.mark.parametrize("pending_provider", ["github", "gitlab"], indirect=True)
@pytest.mark.parametrize("entrypoint", ["owner", "operator"])
@pytest.mark.parametrize("mutation", ["delete", "rebind"])
async def test_pending_admission_serializes_with_connection_changes(
    listener_database,  # noqa: F811 - imported shared PostgreSQL fixture
    pending_provider,
    entrypoint,
    mutation,
):
    database = listener_database
    provider_id, identity, prepared = pending_provider
    async with database.scope() as session:
        user = User(username=f"pending-admission-{uuid4().hex}", password=str(uuid4()), is_active=True)
        session.add(user)
        await session.flush()
        flow = Flow(name="Pending admission", user_id=user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        connections = []
        for name in ("work", "replacement"):
            connection = Connection(
                provider_key=provider_id,
                name=name,
                display_name=name,
                owner_id=user.id,
                allow_non_interactive=True,
                status="ready",
                executing_identity={"identity": identity},
            )
            session.add(connection)
            await session.flush()
            connections.append(connection)
        trigger = Trigger(
            flow_id=flow.id,
            user_id=user.id,
            name="Admission",
            kind=f"{provider_id}.issue",
            provider=provider_id,
            state="paused",
            connection_id=connections[0].id,
            config={"connection": f"{provider_id}/work"},
            public_id=f"admission-{uuid4().hex}",
            signing_secret_encrypted=str(uuid4()),
            admin_paused_at=datetime.now(timezone.utc) if entrypoint == "operator" else None,
        )
        session.add(trigger)
    started = asyncio.Event()
    backend_pid = None

    async def enable():
        nonlocal backend_pid
        async with database.scope() as session:
            row = await session.get(Trigger, trigger.id)
            backend_pid = (await session.exec(text("SELECT pg_backend_pid()"))).scalar_one()
            started.set()
            if entrypoint == "operator":
                return await operator.bulk_resume(
                    session,
                    TriggerService(),
                    request=TriggerBulkRequest(trigger_ids=[trigger.id]),
                    actor_id=user.id,
                )
            return await TriggerService().enable(session, row=row)

    admission = None
    try:
        async with database.scope() as session:
            connection = await session.get(Connection, connections[0].id, with_for_update=True)
            admission = asyncio.create_task(enable())
            await asyncio.wait_for(started.wait(), timeout=5)
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
            if mutation == "delete":
                await asyncio.wait_for(DatabaseConnectionResolverService().delete(session, connection), timeout=10)
            else:
                row = await session.get(Trigger, trigger.id)
                row.connection_id = connections[1].id
                row.config = {"connection": f"{provider_id}/replacement"}
                session.add(row)
                await asyncio.wait_for(session.flush(), timeout=10)
        result = (await asyncio.wait_for(asyncio.gather(admission, return_exceptions=True), timeout=5))[0]
        if entrypoint == "owner":
            assert isinstance(result, ValueError), result
        else:
            assert not isinstance(result, BaseException), result
            assert [failure.trigger_id for failure in result.failed] == [trigger.id]
            assert result.changed == []
        assert prepared == [], "A stale binding reached the provider admission hook"
        async with database.scope() as session:
            assert not (await session.exec(select(TriggerSubscription))).all()
            row = await session.get(Trigger, trigger.id)
            assert row.state == "paused"
            assert row.connection_id == (None if mutation == "delete" else connections[1].id)
            if entrypoint == "operator":
                assert row.admin_paused_at is None
            # A fresh request using the replacement can still persist both FK
            # references. This proves rejection was the race, not a validator
            # that never reached a provider's pending reservation.
            row.connection_id = connections[1].id
            row.config = {"connection": f"{provider_id}/replacement"}
            session.add(row)
            await session.flush()
            enabled = await TriggerService().enable(session, row=row)
            assert enabled.state == "pending"
            reservation = (await session.exec(select(TriggerSubscription))).one()
            assert reservation.connection_id == connections[1].id
            assert reservation.trigger_id == trigger.id
            assert reservation.state == "pending"
        assert prepared == [trigger.id]
    finally:
        if admission is not None:
            admission.cancel()
            await asyncio.gather(admission, return_exceptions=True)
