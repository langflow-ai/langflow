"""Slack Socket Mode in the listener, against a real local WebSocket server.

Every test runs the production supervisor (leases, ledger writes, trigger state
transitions) and the production adapter. Only Slack is fake - and even then
the adapter talks to it over a real socket, so acknowledgements, disconnect
warnings and dropped connections are frames on the wire, not mock calls.
"""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerState
from langflow.services.deps import session_scope
from langflow.services.triggers.constants import MECHANISM_SLACK_SOCKET_MODE, SLACK_TRIGGER_KINDS
from langflow.services.triggers.listeners import adapters, connection_leases
from langflow.services.triggers.listeners.supervisor import ListenerSupervisor
from langflow.services.triggers.providers.slack.socket_mode import (
    PROVIDER_STATE_APP_ID,
    SlackSocketModeAdapter,
)

from tests.unit.services.triggers import slack_fixtures as fx
from tests.unit.services.triggers.fake_slack_socket import API_BASE_URL, FakeSlackSocketMode, local_socket_url

pytestmark = pytest.mark.no_blockbuster

SOCKET = MECHANISM_SLACK_SOCKET_MODE


@pytest.fixture
async def slack():
    async with FakeSlackSocketMode() as fake:
        yield fake


@pytest.fixture
def socket_adapters(slack, monkeypatch):
    """Point the Socket Mode registration at the fake, and restore it afterwards."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "listener_backoff_base_s", 0.05)
    monkeypatch.setattr(settings, "listener_backoff_cap_s", 0.1)
    created: list[SlackSocketModeAdapter] = []

    def factory(_trigger):
        adapter = SlackSocketModeAdapter(
            max_connections=10,
            api_base_url=API_BASE_URL,
            http_transport=slack.transport(),
            url_allowed=local_socket_url,
            open_timeout_s=5.0,
            drain_timeout_s=0.3,
        )
        created.append(adapter)
        return adapter

    saved = {key: adapters._REGISTRY.pop(key) for key in list(adapters._REGISTRY) if key[1] == SOCKET}
    for kind in SLACK_TRIGGER_KINDS:
        adapters.register_adapter(kind=kind, mechanism=SOCKET, factory=factory, rebuild_on_config_change=False)
    try:
        yield created
    finally:
        for kind in SLACK_TRIGGER_KINDS:
            adapters.unregister_adapter(kind=kind, mechanism=SOCKET)
        adapters._REGISTRY.update(saved)


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


@pytest.mark.usefixtures("socket_adapters")
async def test_a_failed_write_leaves_the_envelope_unacknowledged(
    slack, supervisor, trigger_owner, owned_flow, monkeypatch
) -> None:
    """Slack redelivers what it was never told landed; acknowledging first would lose it."""
    from langflow.services.triggers import ledger

    connection_id, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [socket] = await slack.wait_for_sockets(1)

    async def _broken(*_args, **_kwargs):
        msg = "database unavailable"
        raise RuntimeError(msg)

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


@pytest.mark.usefixtures("socket_adapters")
async def test_a_disconnect_warning_opens_the_replacement_before_closing_the_old_socket(
    slack, supervisor, trigger_owner, owned_flow
) -> None:
    _connection, trigger_id = await _armed(trigger_owner, owned_flow)
    await supervisor.reconcile()
    [old] = await slack.wait_for_sockets(1)

    await old.send({"type": "disconnect", "reason": "warning", "debug_info": {"host": "applink-test"}})
    _, new = await slack.wait_for_sockets(2)
    assert not old.closed.is_set(), "the retiring socket stays open while its replacement comes up"

    # Slack may deliver on either socket during the overlap; each is written once.
    await old.deliver(fx.load("message_channel"), envelope_id="env-old")
    await new.deliver(fx.load("message_channel"), envelope_id="env-new")
    assert await old.wait_for_ack("env-old")
    assert await new.wait_for_ack("env-new")

    await asyncio.wait_for(old.closed.wait(), timeout=5)
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
