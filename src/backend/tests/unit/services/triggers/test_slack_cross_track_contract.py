"""Both Slack transports deliver identical Data for the same event.

The contract TRG-5 exists to keep: a flow moves between the Events API (hosted,
reachable self-managed) and Socket Mode (Desktop, firewalled) unchanged. So for
every recorded Slack body, this delivers it both ways - signed over the real
ingress route to an Events API trigger, and inside a Socket Mode envelope over a
real WebSocket to a Socket Mode trigger with the same filters - and demands the
same outcome from each:

* the same decision (both write a row, or neither does);
* the same ledger dedupe key;
* byte-identical flow-facing payload;
* the same derived session id.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import pytest
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.deps import session_scope
from langflow.services.triggers.correlation import derive_session_id
from langflow.services.triggers.listeners.supervisor import ListenerSupervisor

from tests.unit.services.triggers import slack_fixtures as fx

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

URL = f"api/v1/triggers/ingress/slack/apps/{fx.REGISTRATION_ID}"

#: A body from a second workspace the app is installed in. The transports scope
#: it differently on purpose - see
#: ``test_socket_mode_hears_every_workspace_the_app_is_in_and_the_events_api_one``.
OTHER_WORKSPACE = "message_other_team"

#: Every recorded body that is an event (controls and the handshake are not),
#: from the workspace both triggers' connections belong to.
EVENT_FIXTURES = [
    name
    for name in fx.names()
    if name not in {"url_verification", "app_rate_limited", "unsupported_event", OTHER_WORKSPACE}
]

#: Filters wide enough that most fixtures fire, so the comparison covers real
#: payloads rather than two agreeing "nothing happened"s.
PERMISSIVE = {"include_bot_messages": True, "include_edits": True}


@pytest.fixture(autouse=True)
def _slack_app(monkeypatch, listener_process):  # noqa: ARG001 - both are setup
    fx.use_registrations(monkeypatch)


async def _wait_for_app_ids(trigger_ids, *, timeout: float = 5.0) -> None:
    """Socket fan-out reaches another connection's trigger once its hello recorded the app."""
    from langflow.services.triggers.providers.slack.socket_mode import PROVIDER_STATE_APP_ID

    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        async with session_scope() as session:
            states = [(await session.get(Trigger, trigger_id)).provider_state for trigger_id in trigger_ids]
        if all(state.get(PROVIDER_STATE_APP_ID) == fx.APP_ID for state in states):
            return
        if asyncio.get_running_loop().time() > deadline:
            msg = "the sockets never recorded their app"
            raise AssertionError(msg)
        await asyncio.sleep(0.02)


async def _canonical(trigger_id) -> list[tuple[str, str, str]]:
    """``(dedupe key, payload JSON, session id)`` for every row, in key order."""
    rows = await fx.events_for(trigger_id)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        return sorted(
            (row.dedupe_key, json.dumps(row.payload, sort_keys=True), derive_session_id(trigger, row)) for row in rows
        )


@pytest.mark.usefixtures("socket_adapters")
async def test_both_transports_produce_identical_data_for_every_recorded_event(
    client: AsyncClient, slack, trigger_owner, owned_flow
) -> None:
    arms = {}
    for kind in ("slack.message", "slack.reaction"):
        config = PERMISSIVE if kind == "slack.message" else {"reaction_events": "both"}
        arms[kind] = (
            await fx.arm(
                owned_flow, trigger_owner, await fx.make_oauth_connection(trigger_owner), kind=kind, config=config
            ),
            await fx.arm(
                owned_flow,
                trigger_owner,
                await fx.make_app_token_connection(trigger_owner),
                kind=kind,
                mechanism="slack.socket_mode",
                config=config,
            ),
        )
    supervisor = ListenerSupervisor(holder="replica-a")
    try:
        await supervisor.reconcile()
        sockets = await slack.wait_for_sockets(2)
        await _wait_for_app_ids([socket_mode for _events_api, socket_mode in arms.values()])

        for index, name in enumerate(EVENT_FIXTURES):
            body = fx.raw(name)
            response = await client.post(URL, content=body, headers=fx.sign(body))
            assert response.status_code == 202, (name, response.text)
            envelope_id = f"env-{index}"
            # Either socket may carry it; Slack spreads an app's events across them.
            socket = sockets[index % len(sockets)]
            await socket.deliver(fx.load(name), envelope_id=envelope_id)
            assert await socket.wait_for_ack(envelope_id), name
    finally:
        await supervisor.stop()

    fired = 0
    for kind, (events_api, socket_mode) in arms.items():
        over_http, over_socket = await _canonical(events_api), await _canonical(socket_mode)
        assert over_http == over_socket, kind
        fired += len(over_http)
    # The comparison is only worth something if real events went through it.
    assert fired >= 10


async def test_a_thread_stays_one_session_whichever_transport_carried_each_reply(
    client: AsyncClient, trigger_owner, owned_flow
) -> None:
    """A workspace moving between transports mid-thread keeps the thread's memory."""
    trigger_id = await fx.arm(owned_flow, trigger_owner, await fx.make_oauth_connection(trigger_owner))
    replies = fx.thread_replies(3)

    for reply in replies:
        body = json.dumps(reply).encode()
        assert (await client.post(URL, content=body, headers=fx.sign(body))).status_code == 202

    sessions = {session for _key, _payload, session in await _canonical(trigger_id)}
    assert sessions == {"slack:T0TEAM0001:C0SUPPORT1:1700000000.000100"}


@pytest.mark.usefixtures("socket_adapters")
async def test_an_event_seen_on_both_transports_runs_once(
    client: AsyncClient, slack, trigger_owner, owned_flow
) -> None:
    """The shared ``slack:{event_id}`` key collapses a copy arriving on the other transport.

    A trigger re-armed from one transport to the other can see Slack's retry of
    an event on the new transport; it must not run twice.
    """
    socket_connection = await fx.make_app_token_connection(trigger_owner)
    trigger_id = await fx.arm(
        owned_flow, trigger_owner, socket_connection, mechanism="slack.socket_mode", config=PERMISSIVE
    )
    supervisor = ListenerSupervisor(holder="replica-a")
    try:
        await supervisor.reconcile()
        [socket] = await slack.wait_for_sockets(1)
        await socket.deliver(fx.load("message_channel"), envelope_id="env-1")
        assert await socket.wait_for_ack("env-1")
    finally:
        await supervisor.stop()

    # The owner moves the trigger to an app installation; Slack retries the event there.
    oauth_connection = await fx.make_oauth_connection(trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        row.connection_id = oauth_connection
        row.config = {**row.config, "mechanism_id": "slack.events_api"}
        session.add(row)
    body = fx.raw("message_channel")
    response = await client.post(
        URL, content=body, headers={**fx.sign(body), "X-Slack-Retry-Num": "1", "X-Slack-Retry-Reason": "http_timeout"}
    )

    assert response.status_code == 202
    await asyncio.sleep(0)
    assert len(await fx.events_for(trigger_id)) == 1


@pytest.mark.usefixtures("socket_adapters")
async def test_socket_mode_hears_every_workspace_the_app_is_in_and_the_events_api_one(
    client: AsyncClient, slack, trigger_owner, owned_flow
) -> None:
    """The one deliberate difference between the transports: workspace scope.

    An Events API trigger listens through one *installation* of the app, and a
    hosted app is installed in many tenants' workspaces, so each event reaches
    only the triggers installed in the workspace it came from - that is tenant
    isolation. An app-level token belongs to the app, not to a workspace: its
    socket carries the events of every workspace the app is installed in, and
    whoever holds the token can read all of them anyway. So a Socket Mode
    trigger hears them all; a channel filter narrows it.
    """
    events_api = await fx.arm(owned_flow, trigger_owner, await fx.make_oauth_connection(trigger_owner))
    socket_mode = await fx.arm(
        owned_flow,
        trigger_owner,
        await fx.make_app_token_connection(trigger_owner),
        mechanism="slack.socket_mode",
    )
    supervisor = ListenerSupervisor(holder="replica-a")
    try:
        await supervisor.reconcile()
        [socket] = await slack.wait_for_sockets(1)
        body = fx.raw(OTHER_WORKSPACE)
        assert (await client.post(URL, content=body, headers=fx.sign(body))).status_code == 202
        await socket.deliver(fx.load(OTHER_WORKSPACE), envelope_id="env-other")
        assert await socket.wait_for_ack("env-other")
    finally:
        await supervisor.stop()

    assert await fx.events_for(events_api) == []
    [row] = await fx.events_for(socket_mode)
    assert row.payload["team_id"] == fx.OTHER_TEAM_ID
