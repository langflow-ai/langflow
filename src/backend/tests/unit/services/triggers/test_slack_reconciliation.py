"""Saving a flow arms its Slack trigger nodes on the right transport, or says why not.

The node names a connection by its portable handle only. These tests pin how
that handle becomes a connection id and a Slack transport for the flow owner -
from connection metadata alone - and the owner-facing reason recorded whenever
it cannot, including the two deployment rules: no Socket Mode on hosted, no
Events API on Desktop.
"""

from __future__ import annotations

from typing import Any

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerState
from langflow.services.deps import get_trigger_service, session_scope
from langflow.services.triggers.reconciliation import find_trigger_nodes, reconcile_flow_triggers
from sqlmodel import select

from tests.unit.services.triggers import slack_fixtures as fx

pytestmark = pytest.mark.no_blockbuster

MESSAGE_TYPE = "ext:slack:SlackOnMessageTriggerComponent@official"
REACTION_TYPE = "ext:slack:SlackOnReactionTriggerComponent@official"


def _node(node_type: str = MESSAGE_TYPE, node_id: str = "SlackOnMessage-1", **values: Any) -> dict:
    template = {field: {"value": value} for field, value in values.items()}
    return {"id": node_id, "data": {"type": node_type, "node": {"template": template}}}


async def _save(flow_id, owner_id, *nodes) -> Trigger | None:
    async with session_scope() as session:
        await reconcile_flow_triggers(
            session, flow_id=flow_id, owner_id=owner_id, flow_data={"nodes": list(nodes), "edges": []}
        )
    async with session_scope() as session:
        rows = list((await session.exec(select(Trigger).where(Trigger.flow_id == flow_id))).all())
    return rows[0] if len(rows) == 1 else None


async def _connection_name(connection_id) -> str:
    async with session_scope() as session:
        return (await session.get(Connection, connection_id)).name


@pytest.fixture(autouse=True)
def _slack_app(monkeypatch):
    fx.use_registrations(monkeypatch)


# --------------------------------------------------------------------------- #
# Recognising the nodes
# --------------------------------------------------------------------------- #


def test_bundle_trigger_nodes_are_recognised_by_their_namespaced_type() -> None:
    found = find_trigger_nodes(
        {
            "nodes": [
                _node(MESSAGE_TYPE, "m", connection="slack/support"),
                _node(REACTION_TYPE, "r"),
                _node("ext:slack:SlackOnMessageTriggerComponent@extra", "dev"),
                # Same class name in another bundle: not ours.
                _node("ext:evil:SlackOnMessageTriggerComponent@official", "impostor"),
                _node("ext:slack:SlackPostAsAppComponent@official", "action"),
            ]
        }
    )
    assert [(node_id, kind) for node_id, kind, _ in found] == [
        ("m", "slack.message"),
        ("r", "slack.reaction"),
        ("dev", "slack.message"),
    ]
    assert found[0][2]["connection"] == "slack/support"


# --------------------------------------------------------------------------- #
# Deriving the transport
# --------------------------------------------------------------------------- #


async def test_an_app_installation_arms_on_the_events_api(trigger_owner, owned_flow) -> None:
    connection_id = await fx.make_oauth_connection(trigger_owner)
    handle = f"slack/{await _connection_name(connection_id)}"

    row = await _save(owned_flow, trigger_owner, _node(connection=handle, channels=["C0SUPPORT1"]))

    assert row.state == TriggerState.PENDING.value, "appearing on the canvas never arms"
    assert row.last_error is None
    assert row.provider == "slack"
    assert row.connection_id == connection_id
    assert row.config["mechanism_id"] == "slack.events_api"
    assert row.config["channels"] == ["C0SUPPORT1"]
    assert row.name == "Slack: On Message"


async def test_an_app_level_token_arms_on_socket_mode(trigger_owner, owned_flow) -> None:
    connection_id = await fx.make_app_token_connection(trigger_owner)
    handle = f"slack/{await _connection_name(connection_id)}"

    row = await _save(owned_flow, trigger_owner, _node(REACTION_TYPE, "SlackOnReaction-1", connection=handle))

    assert row.connection_id == connection_id
    assert row.config["mechanism_id"] == "slack.socket_mode"
    assert row.kind == "slack.reaction"


async def test_the_same_flow_json_moves_between_transports(trigger_owner, owned_flow) -> None:
    """Replace the connection behind the handle and the next save moves the trigger."""
    installation = await fx.make_oauth_connection(trigger_owner, name="workspace")
    node = _node(connection="slack/workspace")
    assert (await _save(owned_flow, trigger_owner, node)).config["mechanism_id"] == "slack.events_api"

    async with session_scope() as session:
        await session.delete(await session.get(Connection, installation))
    app_token = await fx.make_app_token_connection(trigger_owner, name="workspace")

    row = await _save(owned_flow, trigger_owner, node)
    assert row.connection_id == app_token
    assert row.config["mechanism_id"] == "slack.socket_mode"


async def test_saving_an_unchanged_node_does_not_rewrite_the_row(trigger_owner, owned_flow) -> None:
    connection_id = await fx.make_oauth_connection(trigger_owner)
    node = _node(connection=f"slack/{await _connection_name(connection_id)}")
    first = await _save(owned_flow, trigger_owner, node)

    async with session_scope() as session:
        touched = await reconcile_flow_triggers(
            session, flow_id=owned_flow, owner_id=trigger_owner, flow_data={"nodes": [node], "edges": []}
        )

    assert touched == 0
    assert (await _save(owned_flow, trigger_owner, node)).updated_at == first.updated_at


# --------------------------------------------------------------------------- #
# Why a trigger cannot be armed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("setup", "fragment"),
    [
        ("no_connection", "Choose a Slack connection"),
        ("someone_elses", "no Slack connection named"),
        ("instance", "no Slack connection named"),
        ("unconfigured_registration", "is not configured on this instance"),
        ("no_signing_secret", "has no signing secret"),
        ("user_registration", "user connection cannot receive events"),
        ("manual_bot_token", "cannot receive events"),
        ("bad_channel", "conversation IDs"),
        ("bad_mention_types", "Conversation types cannot be narrowed"),
    ],
)
async def test_a_node_that_cannot_be_armed_records_why(
    trigger_owner, owned_flow, monkeypatch, setup: str, fragment: str
) -> None:
    values: dict[str, Any] = {}
    if setup == "someone_elses":
        connection_id = await fx.make_oauth_connection(await fx.make_user())
        values["connection"] = f"slack/{await _connection_name(connection_id)}"
    elif setup == "instance":
        connection_id = await fx.make_oauth_connection(trigger_owner, ownership_mode="instance")
        values["connection"] = f"slack/{await _connection_name(connection_id)}"
    elif setup in {
        "unconfigured_registration",
        "no_signing_secret",
        "user_registration",
        "bad_channel",
        "bad_mention_types",
    }:
        registrations = {
            "no_signing_secret": {fx.REGISTRATION_ID: fx.registration(signing_secret=None)},
            "user_registration": {fx.REGISTRATION_ID: fx.registration(profile="user", signing_secret=None)},
            "unconfigured_registration": {},
        }
        if setup in registrations:
            fx.use_registrations(monkeypatch, registrations[setup])
        connection_id = await fx.make_oauth_connection(trigger_owner)
        values["connection"] = f"slack/{await _connection_name(connection_id)}"
        if setup == "bad_channel":
            values["channels"] = ["#support"]
        elif setup == "bad_mention_types":
            values.update(mentions_only=True, conversation_types=["im"])
    elif setup == "manual_bot_token":
        connection_id = await fx.make_app_token_connection(trigger_owner, token="xoxb-bot")  # noqa: S106
        async with session_scope() as session:
            row = await session.get(Connection, connection_id)
            row.granted_scopes = ["chat:write"]  # a bot token carries no app-level marker
            session.add(row)
        values["connection"] = f"slack/{row.name}"

    row = await _save(owned_flow, trigger_owner, _node(**values))

    assert row.state == TriggerState.PENDING.value
    assert fragment in (row.last_error or "")
    assert row.config.get("mechanism_id") is None
    assert row.connection_id is None


async def test_hosted_offers_no_socket_mode(trigger_owner, owned_flow, monkeypatch) -> None:
    connection_id = await fx.make_app_token_connection(trigger_owner)
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "hosted")

    row = await _save(owned_flow, trigger_owner, _node(connection=f"slack/{await _connection_name(connection_id)}"))

    assert "Socket Mode is not available" in row.last_error
    assert row.connection_id is None


async def test_desktop_explains_why_the_events_api_is_unavailable(trigger_owner, owned_flow, monkeypatch) -> None:
    connection_id = await fx.make_oauth_connection(trigger_owner)
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "desktop")

    row = await _save(owned_flow, trigger_owner, _node(connection=f"slack/{await _connection_name(connection_id)}"))

    assert "Langflow Desktop receives Slack events over Socket Mode" in row.last_error
    assert "app-level token" in row.last_error


async def test_an_armed_trigger_whose_connection_disappears_is_taken_out_and_comes_back(
    trigger_owner, owned_flow
) -> None:
    connection_id = await fx.make_oauth_connection(trigger_owner, name="workspace")
    node = _node(connection="slack/workspace")
    row = await _save(owned_flow, trigger_owner, node)
    async with session_scope() as session:
        armed = await session.get(Trigger, row.id)
        armed.state = TriggerState.ACTIVE.value
        session.add(armed)
        await session.delete(await session.get(Connection, connection_id))

    broken = await _save(owned_flow, trigger_owner, node)
    assert broken.state == TriggerState.ERROR.value
    assert "no Slack connection named" in broken.last_error

    await fx.make_oauth_connection(trigger_owner, name="workspace")
    healed = await _save(owned_flow, trigger_owner, node)
    assert healed.state == TriggerState.ACTIVE.value
    assert healed.last_error is None


# --------------------------------------------------------------------------- #
# Enabling
# --------------------------------------------------------------------------- #


async def _enable(trigger_id) -> Trigger:
    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        return await get_trigger_service().enable(session, row=row)


async def test_enabling_arms_a_ready_slack_trigger(trigger_owner, owned_flow) -> None:
    connection_id = await fx.make_oauth_connection(trigger_owner)
    row = await _save(owned_flow, trigger_owner, _node(connection=f"slack/{await _connection_name(connection_id)}"))

    enabled = await _enable(row.id)

    assert enabled.state == TriggerState.ACTIVE.value


@pytest.mark.parametrize(
    ("setup", "fragment"),
    [
        ("no_consent", "Allow background runs"),
        ("revoked", "revoked or expired"),
        ("missing_scope", "missing channels:history"),
        ("unarmable", "Choose a Slack connection"),
    ],
)
async def test_enabling_refuses_a_trigger_that_could_not_run(
    trigger_owner, owned_flow, setup: str, fragment: str
) -> None:
    connection_id = await fx.make_oauth_connection(trigger_owner)
    node = _node(connection=f"slack/{await _connection_name(connection_id)}")
    if setup == "unarmable":
        node = _node()
    row = await _save(owned_flow, trigger_owner, node)
    async with session_scope() as session:
        connection = await session.get(Connection, connection_id)
        if setup == "no_consent":
            connection.allow_non_interactive = False
        elif setup == "revoked":
            connection.status = "revoked"
        elif setup == "missing_scope":
            connection.granted_scopes = ["chat:write"]
        session.add(connection)

    with pytest.raises(ValueError, match=fragment):
        await _enable(row.id)
    async with session_scope() as session:
        assert (await session.get(Trigger, row.id)).state == TriggerState.PENDING.value


async def test_a_mentions_only_trigger_needs_only_the_mention_scope(trigger_owner, owned_flow) -> None:
    connection_id = await fx.make_oauth_connection(trigger_owner)
    async with session_scope() as session:
        connection = await session.get(Connection, connection_id)
        connection.granted_scopes = ["app_mentions:read", "chat:write"]
        session.add(connection)
    row = await _save(
        owned_flow,
        trigger_owner,
        _node(connection=f"slack/{await _connection_name(connection_id)}", mentions_only=True),
    )

    assert (await _enable(row.id)).state == TriggerState.ACTIVE.value
