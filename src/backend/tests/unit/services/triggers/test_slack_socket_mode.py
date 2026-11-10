"""Slack Socket Mode in the listener, against a real local WebSocket server.

Every test runs the production supervisor (leases, ledger writes, trigger state
transitions) and the production adapter. Only Slack is fake - and even then
the adapter talks to it over a real socket, so acknowledgements, disconnect
warnings and dropped connections are frames on the wire, not mock calls.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import replace

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerState
from langflow.services.deps import session_scope
from langflow.services.triggers.constants import MECHANISM_SLACK_SOCKET_MODE
from langflow.services.triggers.listeners import connection_leases
from langflow.services.triggers.listeners.supervisor import ListenerSupervisor
from langflow.services.triggers.providers.slack.socket_mode import PROVIDER_STATE_APP_ID, SlackSocketModeAdapter

from tests.unit.services.triggers import slack_fixtures as fx

pytestmark = pytest.mark.no_blockbuster

SOCKET = MECHANISM_SLACK_SOCKET_MODE


@pytest.fixture(autouse=True)
def _in_the_listener(listener_process):
    """These tests play the listener process: the only one an app-level token resolves in."""


@pytest.fixture
async def supervisor():
    replica = ListenerSupervisor(holder="replica-a")
    try:
        yield replica
    finally:
        await replica.stop()


async def _armed(trigger_owner, owned_flow, *, kind: str = "slack.message", config=None, connection_id=None):
    connection_id = connection_id or await fx.make_app_token_connection(trigger_owner)
    trigger_id = await fx.arm(owned_flow, trigger_owner, connection_id, kind=kind, mechanism=SOCKET, config=config)
    return connection_id, trigger_id


async def _trigger(trigger_id) -> Trigger:
    async with session_scope() as session:
        return await session.get(Trigger, trigger_id)


async def _eventually(predicate, *, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        result = predicate()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return
        if asyncio.get_running_loop().time() > deadline:
            msg = "condition not met in time"
            raise AssertionError(msg)
        await asyncio.sleep(0.02)


# --------------------------------------------------------------------------- #
# Delivery: write, then acknowledge
# --------------------------------------------------------------------------- #


@pytest.mark.usefixtures("socket_adapters")
async def test_an_event_is_committed_before_its_envelope_is_acknowledged(
    slack, supervisor, trigger_owner, owned_flow
) -> None:
    _connection, trigger_id = await _armed(trigger_owner, owned_flow)
    rows_at_ack: dict[str, int] = {}

    async def _count_rows(envelope_id: str) -> None:
        rows_at_ack[envelope_id] = len(await fx.events_for(trigger_id))

    slack.on_ack = _count_rows
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)
    assert slack.authorizations == [f"Bearer {fx.APP_TOKEN}"]

    await socket.deliver(fx.load("message_channel"), envelope_id="env-1")

    assert await socket.wait_for_ack("env-1")
    assert rows_at_ack == {"env-1": 1}, "the ledger row must be durable before Slack is told the event landed"
    [row] = await fx.events_for(trigger_id)
    assert row.dedupe_key == "slack:Ev0MSG00001"
    assert row.payload["session_key"] == "slack:T0TEAM0001:C0SUPPORT1:1700000000.000100"


@pytest.mark.usefixtures("socket_adapters")
async def test_a_redelivered_envelope_is_acknowledged_and_runs_once(
    slack, supervisor, trigger_owner, owned_flow
) -> None:
    _connection, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)

    await socket.deliver(fx.load("message_channel"), envelope_id="env-1")
    await socket.deliver(fx.load("message_channel"), envelope_id="env-2", retry_attempt=1)

    assert await socket.wait_for_ack("env-1")
    assert await socket.wait_for_ack("env-2")
    assert len(await fx.events_for(trigger_id)) == 1


def _integrity_error(detail: str) -> Exception:
    from sqlalchemy.exc import IntegrityError

    return IntegrityError("INSERT INTO trigger_event", {}, Exception(detail))


@pytest.mark.usefixtures("socket_adapters")
@pytest.mark.parametrize(
    "error",
    [RuntimeError("database unavailable"), _integrity_error("a constraint on a trigger that still exists")],
    ids=["unavailable", "integrity"],
)
async def test_a_failed_write_leaves_the_envelope_unacknowledged(
    slack, supervisor, trigger_owner, owned_flow, monkeypatch, error: Exception
) -> None:
    """Slack redelivers what it was never told landed; acknowledging first would lose it."""
    from langflow.services.triggers import ledger

    connection_id, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)

    async def _broken(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(ledger, "append_event", _broken)
    await socket.deliver(fx.load("message_channel"), envelope_id="env-lost")

    await asyncio.wait_for(socket.closed.wait(), timeout=5)
    assert not socket.acked("env-lost")
    assert await fx.events_for(trigger_id) == []
    await _eventually(lambda: supervisor.workers[connection_id].consecutive_failures >= 1)
    assert (await _trigger(trigger_id)).state == TriggerState.ACTIVE.value, "a write failure is retried, not disarmed"


@pytest.mark.usefixtures("socket_adapters")
async def test_hello_records_which_app_the_connection_belongs_to(slack, supervisor, trigger_owner, owned_flow) -> None:
    _connection, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    await slack.wait_for_sockets(1)

    async def _recorded() -> bool:
        return (await _trigger(trigger_id)).provider_state.get(PROVIDER_STATE_APP_ID) == fx.APP_ID

    await _eventually(_recorded)


@pytest.mark.usefixtures("socket_adapters")
async def test_one_socket_serves_message_and_reaction_triggers(slack, supervisor, trigger_owner, owned_flow) -> None:
    connection_id, messages = await _armed(trigger_owner, owned_flow)
    _, reactions = await _armed(trigger_owner, owned_flow, kind="slack.reaction", connection_id=connection_id)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)

    await socket.deliver(fx.load("reaction_added"), envelope_id="env-r")
    await socket.deliver(fx.load("message_im"), envelope_id="env-m")

    assert await socket.wait_for_ack("env-m")
    assert [row.payload["type"] for row in await fx.events_for(reactions)] == ["reaction_added"]
    assert [row.payload["type"] for row in await fx.events_for(messages)] == ["message"]
    assert len(slack.sockets) == 1


@pytest.mark.usefixtures("socket_adapters")
async def test_the_apps_own_reply_is_acknowledged_but_never_fires_a_trigger(
    slack, supervisor, trigger_owner, owned_flow
) -> None:
    _connection, trigger_id = await _armed(trigger_owner, owned_flow, config={"include_bot_messages": True})
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)

    await socket.deliver(fx.load("bot_self_echo"), envelope_id="env-echo")

    assert await socket.wait_for_ack("env-echo")
    assert await fx.events_for(trigger_id) == []


# --------------------------------------------------------------------------- #
# Connection lifecycle
# --------------------------------------------------------------------------- #


async def test_a_disconnect_warning_opens_the_replacement_before_closing_the_old_socket(
    slack, supervisor, trigger_owner, owned_flow, socket_adapters, monkeypatch
) -> None:
    _connection, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [old] = await slack.wait_for_sockets(1)
    # This test writes two durable envelopes during the overlap. The fixture's
    # 0.3-second drain is too short for those writes on loaded CI runners.
    monkeypatch.setattr(socket_adapters[0], "_drain_timeout_s", 5.0)

    await old.send({"type": "disconnect", "reason": "warning", "debug_info": {"host": "applink-test"}})
    _, new = await slack.wait_for_sockets(2)
    assert not old.closed.is_set(), "the retiring socket stays open while its replacement comes up"

    # Slack may deliver on either socket during the overlap; each is written once.
    await old.deliver(fx.load("message_channel"), envelope_id="env-old")
    await new.deliver(fx.load("message_channel"), envelope_id="env-new")
    assert await old.wait_for_ack("env-old")
    assert await new.wait_for_ack("env-new")

    await asyncio.wait_for(old.closed.wait(), timeout=10)
    assert not new.closed.is_set()
    assert len(await fx.events_for(trigger_id)) == 1
    assert len(slack.sockets) == 2, "never more than a socket and its replacement"


@pytest.mark.usefixtures("socket_adapters")
async def test_an_abrupt_close_reconnects(slack, supervisor, trigger_owner, owned_flow) -> None:
    _connection, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [first] = await slack.wait_for_sockets(1)
    await first.deliver(fx.load("message_channel"), envelope_id="env-1")
    assert await first.wait_for_ack("env-1")

    await first.drop()
    _, second = await slack.wait_for_sockets(2)
    await second.deliver(fx.load("message_im"), envelope_id="env-2")

    assert await second.wait_for_ack("env-2")
    assert len(await fx.events_for(trigger_id)) == 2


def _record_failures(supervisor, monkeypatch) -> list[Exception]:
    """Every error the supervisor backs off from; reconnecting inside the adapter adds none."""
    failures: list[Exception] = []
    original = supervisor._failed

    async def record(worker, exc) -> None:
        failures.append(exc)
        await original(worker, exc)

    monkeypatch.setattr(supervisor, "_failed", record)
    return failures


@pytest.mark.usefixtures("socket_adapters")
async def test_quiet_sockets_that_stayed_up_reconnect_without_backing_off(
    slack, supervisor, trigger_owner, owned_flow, monkeypatch
) -> None:
    """A quiet workspace can leave a healthy socket silent for hours.

    Two such sockets closing without a warning, however far apart, are two
    routine closes - not a socket failing straight after it reconnected - so the
    adapter reconnects itself instead of handing the supervisor a failure and a
    backoff, during which Slack's events would be lost.
    """
    from langflow.services.triggers.providers.slack import socket_mode

    monkeypatch.setattr(socket_mode, "_STABLE_SOCKET_S", 0.05)
    failures = _record_failures(supervisor, monkeypatch)
    await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()

    [first] = await slack.wait_for_sockets(1)
    await asyncio.sleep(0.1)
    await first.drop()
    _, second = await slack.wait_for_sockets(2)
    await asyncio.sleep(0.1)
    await second.drop()
    await slack.wait_for_sockets(3)

    assert failures == []


@pytest.mark.usefixtures("socket_adapters")
async def test_sockets_that_keep_dropping_straight_after_opening_back_off(
    slack, supervisor, trigger_owner, owned_flow, monkeypatch
) -> None:
    from langflow.services.triggers.providers.slack.socket_mode import SlackSocketClosedError

    failures = _record_failures(supervisor, monkeypatch)
    await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()

    [first] = await slack.wait_for_sockets(1)
    await first.drop()
    _, second = await slack.wait_for_sockets(2)
    await second.drop()

    await _eventually(lambda: any(isinstance(error, SlackSocketClosedError) for error in failures))


@pytest.mark.usefixtures("socket_adapters")
async def test_a_connection_slack_drops_right_after_hello_backs_off_and_says_so(
    slack, supervisor, trigger_owner, owned_flow, monkeypatch
) -> None:
    """Slack's ``hello`` is not proof the connection works; a socket that held is.

    Counting each hello as a success reset the failure count on every attempt,
    so a connection Slack accepted and dropped straight away retried at the
    base backoff for good, and its owner never saw why.
    """
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "listener_failure_threshold", 3)
    counts: list[int] = []
    original = supervisor._failed

    async def record(worker, exc) -> None:
        await original(worker, exc)
        counts.append(worker.consecutive_failures)

    monkeypatch.setattr(supervisor, "_failed", record)
    slack.drop_after_hello = 0.02
    _connection, trigger_id = await _armed(trigger_owner, owned_flow)

    async def _banner_shown() -> bool:
        await supervisor.reconcile()
        return "could not hold this connection" in ((await _trigger(trigger_id)).last_error or "")

    await _eventually(_banner_shown, timeout=10)
    assert counts[:3] == [1, 2, 3]
    assert (await _trigger(trigger_id)).state == TriggerState.ACTIVE.value


@pytest.mark.usefixtures("socket_adapters")
async def test_a_socket_that_holds_clears_the_listeners_banner(
    slack, supervisor, trigger_owner, owned_flow, monkeypatch
) -> None:
    """A quiet workspace can send nothing for hours; a socket that stayed up is the proof it works."""
    from langflow.services.deps import get_settings_service
    from langflow.services.triggers.providers.slack import socket_mode

    monkeypatch.setattr(get_settings_service().settings, "listener_failure_threshold", 1)
    monkeypatch.setattr(socket_mode, "_STABLE_SOCKET_S", 0.2)
    slack.open_errors = [(200, {"ok": False, "error": "missing_scope"})]
    connection_id, trigger_id = await _armed(trigger_owner, owned_flow)

    async def _last_error() -> str | None:
        await supervisor.reconcile()
        return (await _trigger(trigger_id)).last_error

    async def _banner_shown() -> bool:
        return await _last_error() is not None

    async def _banner_cleared() -> bool:
        return await _last_error() is None

    async def _reopened() -> bool:
        await supervisor.reconcile()
        return bool(slack.sockets)

    await _eventually(_banner_shown)
    await _eventually(_reopened)
    await _eventually(_banner_cleared)

    assert supervisor.workers[connection_id].consecutive_failures == 0
    assert slack.open_calls == 2


@pytest.mark.usefixtures("socket_adapters")
async def test_a_rejected_app_token_asks_for_a_reconnect(slack, supervisor, trigger_owner, owned_flow) -> None:
    slack.open_errors = [(200, {"ok": False, "error": "invalid_auth"})]
    _connection, trigger_id = await _armed(trigger_owner, owned_flow)

    await supervisor.reconcile()

    async def _needs_reconnect() -> bool:
        return (await _trigger(trigger_id)).state == TriggerState.NEEDS_RECONNECT.value

    await _eventually(_needs_reconnect)
    assert slack.sockets == []


@pytest.mark.usefixtures("socket_adapters")
async def test_a_bot_token_can_never_open_a_socket(slack, supervisor, trigger_owner, owned_flow) -> None:
    connection_id = await fx.make_app_token_connection(trigger_owner, token="xoxb-not-an-app-token")  # noqa: S106
    _, trigger_id = await _armed(trigger_owner, owned_flow, connection_id=connection_id)

    await supervisor.reconcile()

    async def _needs_reconnect() -> bool:
        return (await _trigger(trigger_id)).state == TriggerState.NEEDS_RECONNECT.value

    await _eventually(_needs_reconnect)
    assert slack.open_calls == 0, "a bot token is never sent to apps.connections.open"


@pytest.mark.usefixtures("socket_adapters")
@pytest.mark.parametrize(
    ("setup", "expected_error"),
    [("disabled", "SlackSocketModeDisabledError"), ("over_budget", "SlackConnectionLimitError")],
)
async def test_app_configuration_problems_back_off_without_disarming(
    slack, supervisor, trigger_owner, owned_flow, setup: str, expected_error: str
) -> None:
    """Socket Mode switched off, or the app's ten sockets in use: retried, never disarmed."""
    if setup == "over_budget":
        slack.num_connections = 11
    connection_id, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)
    if setup == "disabled":
        await socket.send({"type": "disconnect", "reason": "link_disabled"})

    await _eventually(lambda: supervisor.workers[connection_id].last_error == expected_error)
    await asyncio.wait_for(socket.closed.wait(), timeout=5)
    assert (await _trigger(trigger_id)).state == TriggerState.ACTIVE.value


@pytest.mark.usefixtures("socket_adapters")
async def test_editing_a_filter_applies_without_reconnecting(
    slack, supervisor, socket_adapters, trigger_owner, owned_flow
) -> None:
    _connection, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)

    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        row.config = {**row.config, "channels": ["C0RELEASE1"]}
        session.add(row)
    await supervisor.reconcile()

    await socket.deliver(fx.load("message_channel"), envelope_id="env-filtered")
    assert await socket.wait_for_ack("env-filtered")
    assert await fx.events_for(trigger_id) == [], "the edited filter is live on the socket already open"
    assert len(slack.sockets) == 1
    assert len(socket_adapters) == 1, "a filter edit must not rebuild the adapter"


@pytest.mark.usefixtures("socket_adapters")
async def test_a_second_replica_never_opens_a_duplicate_socket(slack, trigger_owner, owned_flow) -> None:
    await _armed(trigger_owner, owned_flow)
    first, second = ListenerSupervisor(holder="replica-a"), ListenerSupervisor(holder="replica-b")
    try:
        await first.reconcile()
        await second.reconcile()
        await slack.wait_for_sockets(1)
        await second.reconcile()
        await asyncio.sleep(0.2)
        assert len(slack.sockets) == 1
    finally:
        await first.stop()
        await second.stop()


@pytest.mark.usefixtures("socket_adapters")
async def test_losing_the_lease_closes_the_socket(slack, supervisor, trigger_owner, owned_flow) -> None:
    connection_id, _ = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)

    async with session_scope() as session:
        await connection_leases.release(session, connection_id=connection_id, holder="replica-a")
        await connection_leases.claim(session, connection_id=connection_id, holder="replica-b", ttl_s=300)
    supervisor.workers[connection_id].last_renewed_at = supervisor.workers[connection_id].last_renewed_at.replace(
        year=2020
    )
    await supervisor.reconcile()

    await asyncio.wait_for(socket.closed.wait(), timeout=5)
    assert connection_id not in supervisor.workers


# --------------------------------------------------------------------------- #
# One app, several connections
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("change", ["pause", "filter-out", "filter-match", "consent", "ownership", "app", "mechanism"])
async def test_a_cached_same_app_target_change_does_not_close_the_receiving_socket(
    slack, supervisor, socket_adapters, trigger_owner, owned_flow, monkeypatch, change
) -> None:
    _, mine = await _armed(trigger_owner, owned_flow)
    failures = _record_failures(supervisor, monkeypatch)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)
    colleague = await fx.make_user()
    _, theirs = await _armed(colleague, await fx.make_flow(colleague))
    async with session_scope() as session:
        row = await session.get(Trigger, theirs)
        row.provider_state = {PROVIDER_STATE_APP_ID: fx.APP_ID}
        session.add(row)

    await socket.deliver(fx.load("message_channel"), envelope_id="env-prime")
    assert await socket.wait_for_ack("env-prime")
    assert len(await fx.events_for(theirs)) == 1
    async with session_scope() as session:
        row = await session.get(Trigger, theirs)
        if change == "pause":
            row.state = TriggerState.PAUSED.value
        elif change in {"filter-out", "filter-match"}:
            channel = "C0RELEASE1" if change == "filter-out" else "C0SUPPORT1"
            row.config = {**row.config, "channels": [channel]}
        elif change in {"consent", "ownership"}:
            connection = await session.get(Connection, row.connection_id)
            if change == "consent":
                connection.allow_non_interactive = False
            else:
                connection.ownership_mode = "instance"
                connection.owner_id = None
            session.add(connection)
        elif change == "app":
            row.provider_state = {PROVIDER_STATE_APP_ID: "A0OTHERAPP"}
        else:
            row.config = {**row.config, "mechanism_id": "slack.events_api"}
        session.add(row)

    for number in (2, 3):
        body = fx.load("message_channel")
        body["event_id"] = f"Ev0FRESH{number}"
        await socket.deliver(body, envelope_id=f"env-fresh-{number}")
        assert await socket.wait_for_ack(f"env-fresh-{number}")
    assert len(await fx.events_for(mine)) == 3
    assert len(await fx.events_for(theirs)) == (3 if change == "filter-match" else 1)
    assert failures == []
    assert not socket.closed.is_set()
    assert len(socket_adapters) == 1


@pytest.mark.parametrize(("channel", "expected"), [("C0RELEASE1", 1), ("C0SUPPORT1", 2)])
async def test_a_filter_edit_before_reconcile_is_rematched_without_reconnecting(
    slack, supervisor, socket_adapters, trigger_owner, owned_flow, channel, expected
) -> None:
    _, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)
    await socket.deliver(fx.load("message_channel"), envelope_id="env-prime")
    assert await socket.wait_for_ack("env-prime")
    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        row.config = {**row.config, "channels": [channel]}
        session.add(row)
    body = fx.load("message_channel")
    body["event_id"] = "Ev0EDITED"
    await socket.deliver(body, envelope_id="env-edited")
    assert await socket.wait_for_ack("env-edited")
    assert len(await fx.events_for(trigger_id)) == expected
    await supervisor.reconcile()
    assert not socket.closed.is_set()
    assert len(socket_adapters) == 1


@pytest.mark.parametrize("phase", ["startup", "overlap"])
async def test_an_event_waits_for_the_inflight_app_identity_write(
    slack, supervisor, socket_adapters, trigger_owner, owned_flow, monkeypatch, phase
) -> None:
    """An acknowledged event must not leave an older app-ID write in flight."""
    initial_write = asyncio.Event()
    release_write = asyncio.Event()
    completed = []
    gate_enabled = phase == "startup"
    original = supervisor._context

    def gated_context(worker):
        ctx = original(worker)

        async def save_cursor(**kwargs):
            if gate_enabled and not initial_write.is_set():
                initial_write.set()
                await release_write.wait()
            await ctx.save_cursor(**kwargs)
            completed.append(kwargs["trigger_id"])

        return replace(ctx, save_cursor=save_cursor)

    monkeypatch.setattr(supervisor, "_context", gated_context)
    _, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)
    peer = None
    if phase == "overlap":
        await socket.deliver(fx.load("message_im"), envelope_id="env-initial")
        assert await socket.wait_for_ack("env-initial")
        socket_adapters[0]._drain_timeout_s = 10.0
        await socket.send({"type": "disconnect", "reason": "warning"})
        _, peer = await slack.wait_for_sockets(2)
        await peer.deliver(fx.load("message_im"), envelope_id="env-replacement")
        assert await peer.wait_for_ack("env-replacement")
        async with session_scope() as session:
            row = await session.get(Trigger, trigger_id)
            row.provider_state = {}
            session.add(row)
        await supervisor.reconcile()
        completed.clear()
        gate_enabled = True
    await socket.deliver(fx.load("message_channel"), envelope_id="env-prime")
    await asyncio.wait_for(initial_write.wait(), timeout=5)
    try:
        if peer is not None:
            await peer.deliver(fx.load("message_channel"), envelope_id="env-peer")
        assert not await socket.wait_for_ack("env-prime", timeout=0.5)
        if peer is not None:
            assert not peer.acked("env-peer")
        assert len(await fx.events_for(trigger_id)) == (0 if phase == "startup" else 1)
        assert completed == []
    finally:
        release_write.set()
    assert await socket.wait_for_ack("env-prime")
    if peer is not None:
        assert await peer.wait_for_ack("env-peer")
    assert completed == [trigger_id]
    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        row.config = {**row.config, "channels": ["C0SUPPORT1"]}
        session.add(row)
    body = fx.load("message_channel")
    body["event_id"] = "Ev0AFTERINITIAL"
    await socket.deliver(body, envelope_id="env-after-initial")
    assert await socket.wait_for_ack("env-after-initial")
    assert len(await fx.events_for(trigger_id)) == (2 if phase == "startup" else 3)
    assert not socket.closed.is_set()
    assert len(socket_adapters) == 1


@pytest.mark.usefixtures("socket_adapters")
async def test_stop_cancels_a_pending_app_identity_write_and_its_waiting_event(
    slack, supervisor, trigger_owner, owned_flow, monkeypatch
) -> None:
    initial_write = asyncio.Event()
    release_write = asyncio.Event()
    original = supervisor._context

    def gated_context(worker):
        ctx = original(worker)

        async def save_cursor(**kwargs):
            initial_write.set()
            await release_write.wait()
            await ctx.save_cursor(**kwargs)

        return replace(ctx, save_cursor=save_cursor)

    monkeypatch.setattr(supervisor, "_context", gated_context)
    _, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)
    await asyncio.wait_for(initial_write.wait(), timeout=5)
    try:
        await socket.deliver(fx.load("message_channel"), envelope_id="env-pending")
        await asyncio.wait_for(supervisor.stop(), timeout=5)
        await asyncio.wait_for(socket.closed.wait(), timeout=5)
        assert not socket.acked("env-pending")
        assert await fx.events_for(trigger_id) == []
    finally:
        release_write.set()


@pytest.mark.parametrize("change", ["pause", "lease", "ownership", "consent", "binding", "mechanism", "app"])
@pytest.mark.usefixtures("socket_adapters")
async def test_a_changed_slack_source_still_rejects_the_envelope(
    slack, supervisor, trigger_owner, owned_flow, change
) -> None:
    connection_id, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)
    await socket.deliver(fx.load("message_channel"), envelope_id="env-prime")
    assert await socket.wait_for_ack("env-prime")
    replacement = await fx.make_app_token_connection(trigger_owner) if change == "binding" else None
    async with session_scope() as session:
        if change in {"ownership", "consent"}:
            connection = await session.get(Connection, connection_id)
            if change == "ownership":
                connection.ownership_mode = "instance"
                connection.owner_id = None
            else:
                connection.allow_non_interactive = False
            session.add(connection)
        elif change != "lease":
            row = await session.get(Trigger, trigger_id)
            if change == "pause":
                row.state = TriggerState.PAUSED.value
            elif change == "binding":
                row.connection_id = replacement
            elif change == "mechanism":
                row.config = {**row.config, "mechanism_id": "slack.events_api"}
            else:
                row.provider_state = {PROVIDER_STATE_APP_ID: "A0OTHERAPP"}
            session.add(row)
        else:
            await connection_leases.release(session, connection_id=connection_id, holder="replica-a")
            await connection_leases.claim(session, connection_id=connection_id, holder="replica-b", ttl_s=300)
    await socket.deliver(fx.load("message_im"), envelope_id="env-rejected")
    await asyncio.wait_for(socket.closed.wait(), timeout=5)
    assert not socket.acked("env-rejected")
    assert len(await fx.events_for(trigger_id)) == 1


@pytest.mark.parametrize("change", ["lease", "consent", "binding"])
@pytest.mark.usefixtures("socket_adapters")
async def test_a_stale_destination_does_not_hide_lost_source_authority(
    slack, supervisor, trigger_owner, owned_flow, change
) -> None:
    connection_id, mine = await _armed(trigger_owner, owned_flow, config={"channels": ["C0SUPPORT1"]})
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)
    colleague = await fx.make_user()
    _, theirs = await _armed(colleague, await fx.make_flow(colleague))
    async with session_scope() as session:
        row = await session.get(Trigger, theirs)
        row.provider_state = {PROVIDER_STATE_APP_ID: fx.APP_ID}
        session.add(row)
    await socket.deliver(fx.load("message_channel"), envelope_id="env-prime")
    assert await socket.wait_for_ack("env-prime")
    replacement = await fx.make_app_token_connection(trigger_owner) if change == "binding" else None
    async with session_scope() as session:
        row = await session.get(Trigger, theirs)
        row.state = TriggerState.PAUSED.value
        session.add(row)
        if change == "lease":
            await connection_leases.release(session, connection_id=connection_id, holder="replica-a")
            await connection_leases.claim(session, connection_id=connection_id, holder="replica-b", ttl_s=300)
        elif change == "consent":
            connection = await session.get(Connection, connection_id)
            connection.allow_non_interactive = False
            session.add(connection)
        else:
            source = await session.get(Trigger, mine)
            source.connection_id = replacement
            session.add(source)
    # The source filter excludes this event. Its only cached destination was
    # paused, but that soft destination miss cannot excuse an invalid source.
    await socket.deliver(fx.load("message_im"), envelope_id="env-rejected")
    await asyncio.wait_for(socket.closed.wait(), timeout=5)
    assert not socket.acked("env-rejected")
    assert len(await fx.events_for(mine)) == len(await fx.events_for(theirs)) == 1


@pytest.mark.usefixtures("socket_adapters")
async def test_a_second_destination_edit_leaves_the_envelope_unacknowledged(
    slack, supervisor, trigger_owner, owned_flow, monkeypatch
) -> None:
    _, mine = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)
    colleague = await fx.make_user()
    _, theirs = await _armed(colleague, await fx.make_flow(colleague))
    async with session_scope() as session:
        row = await session.get(Trigger, theirs)
        row.provider_state = {PROVIDER_STATE_APP_ID: fx.APP_ID}
        session.add(row)
    await socket.deliver(fx.load("message_channel"), envelope_id="env-prime")
    assert await socket.wait_for_ack("env-prime")
    async with session_scope() as session:
        row = await session.get(Trigger, theirs)
        row.config = {**row.config, "channels": ["C0SUPPORT1"]}
        session.add(row)
    original = SlackSocketModeAdapter._load_same_app_triggers
    refreshed = []

    async def edit_after_read(adapter, ctx, *, target_id=None):
        targets = await original(adapter, ctx, target_id=target_id)
        if target_id is not None:
            refreshed.append(target_id)
            async with session_scope() as session:
                row = await session.get(Trigger, target_id)
                row.config = {**row.config, "channels": ["C0RELEASE1"]}
                session.add(row)
        return targets

    monkeypatch.setattr(SlackSocketModeAdapter, "_load_same_app_triggers", edit_after_read)
    body = fx.load("message_channel")
    body["event_id"] = "Ev0RACING"
    await socket.deliver(body, envelope_id="env-racing")
    await asyncio.wait_for(socket.closed.wait(), timeout=5)
    assert not socket.acked("env-racing")
    assert refreshed == [theirs]
    assert len(await fx.events_for(mine)) == 2
    assert len(await fx.events_for(theirs)) == 1


@pytest.mark.usefixtures("socket_adapters")
async def test_an_event_on_one_socket_reaches_every_connection_of_the_same_app(
    slack, supervisor, trigger_owner, owned_flow
) -> None:
    """Slack spreads an app's events across all its sockets; none may be lost to the wrong one."""
    _, mine = await _armed(trigger_owner, owned_flow)
    colleague = await fx.make_user()
    _, theirs = await _armed(colleague, await fx.make_flow(colleague))
    await supervisor.reconcile()
    first, second = await slack.wait_for_sockets(2)

    async def _both_recorded() -> bool:
        states = [(await _trigger(trigger_id)).provider_state for trigger_id in (mine, theirs)]
        return all(state.get(PROVIDER_STATE_APP_ID) == fx.APP_ID for state in states)

    await _eventually(_both_recorded)

    await first.deliver(fx.load("message_channel"), envelope_id="env-a")
    await second.deliver(fx.load("message_im"), envelope_id="env-b")
    assert await first.wait_for_ack("env-a")
    assert await second.wait_for_ack("env-b")

    for trigger_id in (mine, theirs):
        assert sorted(row.payload["slack_event_id"] for row in await fx.events_for(trigger_id)) == [
            "Ev0MSG00001",
            "Ev0MSG00003",
        ]


@pytest.mark.usefixtures("socket_adapters")
async def test_a_different_app_on_the_same_instance_is_not_fanned_out_to(
    slack, supervisor, trigger_owner, owned_flow
) -> None:
    _, mine = await _armed(trigger_owner, owned_flow)
    colleague = await fx.make_user()
    _, other_app = await _armed(colleague, await fx.make_flow(colleague))
    async with session_scope() as session:
        row = await session.get(Trigger, other_app)
        row.state = TriggerState.PAUSED.value  # keep its own socket out of this test
        row.provider_state = {PROVIDER_STATE_APP_ID: "A0SOMEOTHER"}
        session.add(row)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)

    async with session_scope() as session:
        row = await session.get(Trigger, other_app)
        row.state = TriggerState.ACTIVE.value
        session.add(row)

    await socket.deliver(fx.load("message_channel"), envelope_id="env-1")
    assert await socket.wait_for_ack("env-1")

    assert len(await fx.events_for(mine)) == 1
    assert await fx.events_for(other_app) == []


@pytest.mark.usefixtures("socket_adapters")
async def test_a_trigger_deleted_since_it_was_targeted_is_skipped_not_fatal(
    slack, supervisor, trigger_owner, owned_flow, monkeypatch
) -> None:
    """Postgres refuses a ledger row for a deleted trigger; the socket must survive it.

    With the cross-connection fan-out, another person deleting their flow is
    enough to leave a trigger that no longer exists in this socket's targets
    for up to one cache interval. SQLite does not enforce the foreign key, so
    Postgres's refusal is reproduced here.
    """
    from langflow.services.triggers import ledger
    from langflow.services.triggers.cleanup import delete_triggers

    _, mine = await _armed(trigger_owner, owned_flow)
    colleague = await fx.make_user()
    _, theirs = await _armed(colleague, await fx.make_flow(colleague))
    failures = _record_failures(supervisor, monkeypatch)
    original = ledger.append_event

    async def _foreign_key_enforced(session, *, trigger_id, **kwargs):
        if await session.get(Trigger, trigger_id) is None:
            detail = 'insert or update on table "trigger_event" violates foreign key constraint'
            raise _integrity_error(detail)
        return await original(session, trigger_id=trigger_id, **kwargs)

    monkeypatch.setattr(ledger, "append_event", _foreign_key_enforced)
    await supervisor.reconcile()
    first, _second = await slack.wait_for_sockets(2)

    async def _both_recorded() -> bool:
        states = [(await _trigger(trigger_id)).provider_state for trigger_id in (mine, theirs)]
        return all(state.get(PROVIDER_STATE_APP_ID) == fx.APP_ID for state in states)

    await _eventually(_both_recorded)
    await first.deliver(fx.load("message_channel"), envelope_id="env-1")
    assert await first.wait_for_ack("env-1")
    async with session_scope() as session:
        await delete_triggers(session, trigger_ids=[theirs])

    await first.deliver(fx.load("message_im"), envelope_id="env-2")

    assert await first.wait_for_ack("env-2")
    assert len(await fx.events_for(mine)) == 2
    assert failures == []
    assert not first.closed.is_set()


@pytest.mark.usefixtures("socket_adapters")
async def test_a_trigger_that_comes_back_to_the_connection_has_its_app_recorded_again(
    slack, supervisor, trigger_owner, owned_flow
) -> None:
    """Moving a trigger off a connection forgets its app; moving it back has to record it again.

    Otherwise colleagues' sockets for the app would never find it, and it would
    silently miss the share of events Slack sends to them.
    """
    connection_id, first = await _armed(trigger_owner, owned_flow)
    _, second = await _armed(trigger_owner, owned_flow, connection_id=connection_id)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)

    async def _recorded(trigger_id) -> bool:
        return (await _trigger(trigger_id)).provider_state.get(PROVIDER_STATE_APP_ID) == fx.APP_ID

    await _eventually(lambda: _recorded(first))
    await _eventually(lambda: _recorded(second))
    async with session_scope() as session:
        # What a move to another connection and back leaves, with no event between.
        row = await session.get(Trigger, second)
        row.provider_state = {}
        session.add(row)
    await supervisor.reconcile()

    await socket.deliver(fx.load("message_channel"), envelope_id="env-1")

    assert await socket.wait_for_ack("env-1")
    assert await _recorded(second)


# --------------------------------------------------------------------------- #
# Lifecycle edges: no socket outlives the adapter, and a refresh never leaves
# the connection without a live socket
# --------------------------------------------------------------------------- #


@pytest.mark.usefixtures("socket_adapters")
async def test_a_socket_cancelled_mid_handshake_is_closed(slack, supervisor, trigger_owner, owned_flow) -> None:
    """A lost lease or a stop can land between connect and hello; the socket counts against Slack's ten."""
    slack.hello_delay = 3.0
    await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)

    await supervisor.stop()

    await asyncio.wait_for(socket.closed.wait(), timeout=5)


async def test_stop_racing_a_running_start_never_reconnects(slack) -> None:
    """``stop()`` without cancelling ``start()`` first must still leave nothing open."""
    from types import SimpleNamespace
    from uuid import uuid4

    from langflow.services.triggers.listeners.adapters import ListenerContext
    from pydantic import SecretStr

    from tests.unit.services.triggers.fake_slack_socket import API_BASE_URL, local_socket_url

    async def _credential(_trigger_id=None):
        return SimpleNamespace(access_token=SecretStr(fx.APP_TOKEN))

    async def _noop(**_kwargs):
        return True

    adapter = SlackSocketModeAdapter(
        api_base_url=API_BASE_URL, http_transport=slack.transport(), url_allowed=local_socket_url
    )
    ctx = ListenerContext(
        connection_id=uuid4(),
        triggers=[],
        emit=_noop,
        save_cursor=_noop,
        resolve_credential=_credential,
        stopping=asyncio.Event(),
    )
    running = asyncio.create_task(adapter.start(ctx))
    try:
        [socket] = await slack.wait_for_sockets(1)

        await adapter.stop()

        await asyncio.wait_for(running, timeout=5)
        await asyncio.wait_for(socket.closed.wait(), timeout=5)
        await asyncio.sleep(0.2)
        assert len(slack.sockets) == 1, "nothing may reconnect after stop()"
    finally:
        running.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await running


@pytest.mark.usefixtures("socket_adapters")
async def test_back_to_back_disconnect_warnings_keep_a_live_socket_within_two(
    slack, supervisor, socket_adapters, trigger_owner, owned_flow
) -> None:
    """A second warning, for the replacement, arrives while the first socket is still draining."""
    _, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [first] = await slack.wait_for_sockets(1)
    socket_adapters[0]._drain_timeout_s = 5.0  # keep the first socket draining throughout

    await first.send({"type": "disconnect", "reason": "warning"})
    _, second = await slack.wait_for_sockets(2)
    await second.send({"type": "refresh_requested", "reason": "refresh_requested"})
    await second.send({"type": "disconnect", "reason": "refresh_requested"})
    _, _, third = await slack.wait_for_sockets(3)

    assert not second.closed.is_set(), "the replacement opens before the retiring socket closes"
    await asyncio.wait_for(first.closed.wait(), timeout=5)  # its drain was cut short to make room
    assert slack.max_live <= 2
    await third.deliver(fx.load("message_channel"), envelope_id="env-third")
    assert await third.wait_for_ack("env-third")
    assert len(await fx.events_for(trigger_id)) == 1


@pytest.mark.usefixtures("socket_adapters")
async def test_a_burst_of_events_reads_the_same_app_triggers_once(
    slack, supervisor, socket_adapters, trigger_owner, owned_flow, monkeypatch
) -> None:
    """Cross-connection targets are cached per reconcile interval, not re-queried per event."""
    await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)
    adapter = socket_adapters[0]
    adapter._same_app_ttl_s = 60.0
    loads = 0
    original = adapter._load_same_app_triggers

    async def _counting(ctx):
        nonlocal loads
        loads += 1
        return await original(ctx)

    monkeypatch.setattr(adapter, "_load_same_app_triggers", _counting)
    for index in range(5):
        body = fx.load("message_channel")
        body["event_id"] = f"Ev0BURST{index:03d}"
        await socket.deliver(body, envelope_id=f"env-burst-{index}")
    assert await socket.wait_for_ack("env-burst-4")

    assert loads == 1
