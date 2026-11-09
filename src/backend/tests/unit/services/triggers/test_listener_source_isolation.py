"""Polling failures stay on the source whose configuration needs attention."""

from uuid import uuid4

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.deps import session_scope
from langflow.services.triggers.listeners import adapters
from langflow.services.triggers.listeners.supervisor import ListenerSupervisor
from langflow.services.triggers.source_errors import SourceConfigurationError
from langflow.services.triggers.source_poll import SourceRound
from lfx.integrations.errors import InvalidRequestError
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster
KIND = "source_isolation_test"


@pytest.fixture
async def polling_sources(trigger_owner, make_trigger, monkeypatch):
    async with session_scope() as session:
        connection = Connection(
            provider_key="selftest",
            name=f"source_{uuid4().hex[:8]}",
            display_name="Source isolation",
            ownership_mode="user",
            owner_id=trigger_owner,
            status="ready",
            allow_non_interactive=True,
        )
        session.add(connection)
        await session.flush()
        connection_id = connection.id
    ids = [
        await make_trigger(kind=KIND, provider="selftest", connection_id=connection_id, config={"source": value})
        for value in ("bad", "good")
    ]

    async def lease(*_args, **_kwargs):
        return None

    monkeypatch.setattr("langflow.services.triggers.source_clients.source_lease", lease)
    monkeypatch.setattr(adapters.ProviderSourcePollAdapter, "_supports", staticmethod(lambda _snapshot: True))
    monkeypatch.setattr(adapters, "_REGISTRY", {})
    adapters.register_adapter(
        kind=KIND,
        mechanism=None,
        factory=lambda _: adapters.ProviderSourcePollAdapter(interval_s=3600),
        rebuild_on_config_change=False,
    )
    supervisor = ListenerSupervisor(holder="source-isolation-test")
    # Drive polls explicitly so state assertions do not race a timer.
    monkeypatch.setattr(supervisor, "_spawn", lambda _worker: None)
    await supervisor.reconcile()
    worker = supervisor.workers[connection_id]
    yield supervisor, worker, ids
    await supervisor.stop()


def source_round(trigger):
    return SourceRound(
        items=[{"provider": "selftest", "resource": "items", "id": "1", "version": "1", "data": {}}],
        cursor={"complete": True},
        previous_cursor=dict(trigger.provider_state),
        baseline=False,
        snapshot_resource=None,
        connection_id=trigger.connection_id,
        mechanism_id=None,
        config=dict(trigger.config),
    )


async def test_configuration_error_isolated_from_healthy_source_and_clears_after_edit(polling_sources, monkeypatch):
    supervisor, worker, (bad_id, good_id) = polling_sources

    async def collect(trigger, _lease):
        if trigger.config["source"] == "bad":
            msg = "The project exceeds 5000 issues. Add an issue type filter."
            raise SourceConfigurationError(msg)
        return source_round(trigger)

    monkeypatch.setattr("langflow.services.triggers.source_poll.collect_source", collect)
    ctx = supervisor._context(worker)
    assert await worker.adapter.poll(ctx) == 1
    # Both source orderings preserve the failing source's message.
    worker.triggers.reverse()
    assert await worker.adapter.poll(ctx) == 0
    async with session_scope() as session:
        bad = await session.get(Trigger, bad_id)
        good = await session.get(Trigger, good_id)
        assert bad.last_error == "Source polling failed. The project exceeds 5000 issues. Add an issue type filter."
        assert bad.state == good.state == "active"
        assert bad.provider_state == {}
        assert good.last_error is None
        assert good.provider_state == {"complete": True}
        assert len((await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == good_id))).all()) == 1
        assert not (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == bad_id))).all()
        bad.config = {"source": "fixed"}
        session.add(bad)
    await supervisor.reconcile()
    assert await worker.adapter.poll(ctx) == 1
    async with session_scope() as session:
        assert (await session.get(Trigger, bad_id)).last_error is None
        assert (await session.get(Trigger, good_id)).last_error is None
    assert worker.consecutive_failures == 0


async def test_connection_recovery_keeps_another_sources_configuration_error(polling_sources, monkeypatch):
    supervisor, worker, (bad_id, good_id) = polling_sources

    async def collect(trigger, _lease):
        if trigger.id == bad_id:
            msg = "Narrow this source's filter."
            raise SourceConfigurationError(msg)
        return source_round(trigger)

    monkeypatch.setattr("langflow.services.triggers.source_poll.collect_source", collect)
    ctx = supervisor._context(worker)
    assert await worker.adapter.poll(ctx) == 1
    worker.consecutive_failures = 6
    worker.succeeded_since_failure = False
    async with session_scope() as session:
        good = await session.get(Trigger, good_id)
        good.last_error = "The listener could not hold this connection."
        session.add(good)
    assert await worker.adapter.poll(ctx) == 0
    async with session_scope() as session:
        assert (await session.get(Trigger, bad_id)).last_error == "Source polling failed. Narrow this source's filter."
        assert (await session.get(Trigger, good_id)).last_error is None
    assert worker.consecutive_failures == 0


async def test_provider_input_error_is_not_copied_into_source_status(polling_sources, monkeypatch):
    supervisor, worker, ids = polling_sources

    async def collect(_trigger, _lease):
        msg = "An untrusted provider message with private details"
        raise InvalidRequestError(msg)

    monkeypatch.setattr("langflow.services.triggers.source_poll.collect_source", collect)
    with pytest.raises(InvalidRequestError):
        await worker.adapter.poll(supervisor._context(worker))
    async with session_scope() as session:
        for identifier in ids:
            assert (await session.get(Trigger, identifier)).last_error is None


@pytest.mark.parametrize(
    ("banner", "expected"),
    [
        ("Source polling failed. Old filter failed.", None),
        ("The listener could not hold this connection after 6 attempts.", None),
        ("Source reconciliation failed. Webhook setup failed.", "Source reconciliation failed. Webhook setup failed."),
    ],
)
async def test_success_clears_own_persisted_errors_without_erasing_other_workers(
    polling_sources, monkeypatch, banner, expected
):
    supervisor, worker, (_bad_id, good_id) = polling_sources
    worker.triggers[:] = [snapshot for snapshot in worker.triggers if snapshot.id == good_id]
    async with session_scope() as session:
        row = await session.get(Trigger, good_id)
        row.last_error = banner
        session.add(row)

    async def collect(trigger, _lease):
        return source_round(trigger)

    monkeypatch.setattr("langflow.services.triggers.source_poll.collect_source", collect)
    assert await worker.adapter.poll(supervisor._context(worker)) == 1
    async with session_scope() as session:
        assert (await session.get(Trigger, good_id)).last_error == expected


@pytest.mark.parametrize("terminal", [False, True])
async def test_stale_source_error_cannot_overwrite_changed_configuration(polling_sources, monkeypatch, terminal):
    supervisor, worker, (bad_id, _good_id) = polling_sources
    worker.triggers[:] = [snapshot for snapshot in worker.triggers if snapshot.id == bad_id]

    async def collect(trigger, _lease):
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            row.config = {"source": "fixed"}
            session.add(row)
        msg = "Old settings failed."
        raise SourceConfigurationError(msg, terminal=terminal)

    monkeypatch.setattr("langflow.services.triggers.source_poll.collect_source", collect)
    with pytest.raises(adapters.ListenerDeliveryRejectedError):
        await worker.adapter.poll(supervisor._context(worker))
    async with session_scope() as session:
        assert (await session.get(Trigger, bad_id)).last_error is None
        assert (await session.get(Trigger, bad_id)).state == "active"


async def test_success_does_not_clear_a_concurrent_source_error(polling_sources, monkeypatch):
    supervisor, worker, (_bad_id, good_id) = polling_sources
    worker.triggers[:] = [snapshot for snapshot in worker.triggers if snapshot.id == good_id]

    async def collect(trigger, _lease):
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            row.last_error = "Source polling failed. A newer poll failed."
            session.add(row)
        return source_round(trigger)

    monkeypatch.setattr("langflow.services.triggers.source_poll.collect_source", collect)
    assert await worker.adapter.poll(supervisor._context(worker)) == 1
    async with session_scope() as session:
        assert (await session.get(Trigger, good_id)).last_error == "Source polling failed. A newer poll failed."
