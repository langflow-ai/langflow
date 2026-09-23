"""The identity a trigger run executes as, and its fail-closed connection gate.

Referenced by ``scripts/ci/execution_principal_matrix.json`` for the
``trigger_push`` and ``trigger_listener`` families. A trigger has no caller: it
runs as its owner, non-interactively, and a connection that has not opted into
unattended use must stop the run before a job exists.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.trigger.schemas import TriggerEventState, TriggerState
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher, ledger
from langflow.services.triggers.constants import (
    ACTOR_TRIGGER_DISPATCHER,
    FAMILY_TRIGGER_PUSH,
    TRIGGER_EVENT_FIELD,
)
from langflow.services.triggers.principal import connection_preflight, trigger_execution_principal

pytestmark = pytest.mark.no_blockbuster

# A payload shaped like an attempt to steer the owner's flow. Synthetic value,
# never a credential.
_HOSTILE_TWEAKS = {"ChatInput-1": {"api_key": "attacker"}}  # pragma: allowlist secret


async def _connection(owner_id, *, allow_non_interactive: bool, ownership_mode: str = "user"):
    async with session_scope() as session:
        row = Connection(
            provider_key="slack",
            name=f"bot_{uuid4().hex[:6]}",
            display_name="Slack bot",
            ownership_mode=ownership_mode,
            status="ready",
            health="healthy",
            granted_scopes=["chat:write"],
            executing_identity={"identity": "user_delegated"},
            allow_non_interactive=allow_non_interactive,
            owner_id=owner_id if ownership_mode == "user" else None,
        )
        session.add(row)
        await session.flush()
        return row.id


async def test_trigger_principal_is_the_flow_owner_and_never_anonymous(make_trigger) -> None:
    """Never anonymous, never interactive: an unattended run has no caller to borrow."""
    trigger_id = await make_trigger()
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        principal = trigger_execution_principal(trigger, family=FAMILY_TRIGGER_PUSH)

    assert principal.kind == "flow_owner"
    assert principal.kind not in {"anonymous_public", "unknown"}
    assert principal.interactive is False
    assert principal.user_id == str(trigger.user_id)
    assert principal.family == FAMILY_TRIGGER_PUSH
    assert principal.actor_label == ACTOR_TRIGGER_DISPATCHER


async def test_trigger_tweaks_are_server_generated_and_never_caller_supplied(
    make_trigger, fake_background_service
) -> None:
    """The matrix classifies trigger tweaks as ``server_generated``.

    The dispatcher does build one tweak — the firing event, on the trigger's own
    canvas node, under the single reserved field. Nothing from the event
    *payload* may join it: a provider that could set tweaks would be choosing
    which credentials the owner's flow uses.
    """
    trigger_id = await make_trigger(node_id="ScheduleTrigger-node")
    async with session_scope() as session:
        await ledger.append_event(
            session,
            trigger_id=trigger_id,
            dedupe_key="hostile",
            payload={"tweaks": _HOSTILE_TWEAKS, "data": {"nodes": ["attacker"]}},
        )

    assert await dispatcher.run_once(owner="solo") == 1
    request = fake_background_service.submits[0]["request"]
    # Exactly one node, exactly one field on it.
    assert set(request["tweaks"]) == {"ScheduleTrigger-node"}
    assert set(request["tweaks"]["ScheduleTrigger-node"]) == {TRIGGER_EVENT_FIELD}
    assert "ChatInput-1" not in request["tweaks"]
    # The unpinned run carries no canvas override either, however the payload asks.
    assert "data" not in request
    # The hostile keys survive only as inert data inside the event the component reads.
    event = json.loads(request["tweaks"]["ScheduleTrigger-node"][TRIGGER_EVENT_FIELD])
    assert event["payload"]["tweaks"] == _HOSTILE_TWEAKS


async def test_a_trigger_with_no_canvas_node_sends_no_tweak(make_trigger, fake_background_service) -> None:
    """An API-created trigger names no node to feed, so it overrides nothing."""
    trigger_id = await make_trigger(node_id=None)
    async with session_scope() as session:
        await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="no-node")

    assert await dispatcher.run_once(owner="solo") == 1
    assert fake_background_service.submits[0]["request"]["tweaks"] == {}


async def test_trigger_on_a_connection_without_the_optin_fails_closed(
    make_trigger, trigger_owner, fake_background_service
) -> None:
    """No opt-in, no unattended run — and no job to inspect afterwards."""
    connection_id = await _connection(trigger_owner, allow_non_interactive=False)
    trigger_id = await make_trigger(connection_id=connection_id)

    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert await connection_preflight(session, trigger) is not None

    event_id = await _append(trigger_id)
    assert await dispatcher.run_once(owner="solo") == 0
    assert fake_background_service.submits == []

    async with session_scope() as session:
        event = await session.get(TriggerEvent, event_id)
        trigger = await session.get(Trigger, trigger_id)
    assert event.state == TriggerEventState.FAILED.value
    assert event.error == "connection_not_authorized"
    assert event.job_id is None
    # The owner is told what to do about it.
    assert trigger.state == TriggerState.NEEDS_RECONNECT.value


async def test_trigger_on_a_connection_with_the_optin_is_authorized(
    make_trigger, trigger_owner, fake_background_service
) -> None:
    connection_id = await _connection(trigger_owner, allow_non_interactive=True)
    trigger_id = await make_trigger(connection_id=connection_id)

    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert await connection_preflight(session, trigger) is None

    await _append(trigger_id)
    assert await dispatcher.run_once(owner="solo") == 1
    assert len(fake_background_service.submits) == 1
    assert fake_background_service.submits[0]["user_id"] == trigger_owner


async def test_a_connection_owned_by_somebody_else_never_resolves_for_a_trigger(
    make_trigger, fake_background_service
) -> None:
    """Even with the opt-in set, a trigger may not borrow another user's connection."""
    stranger_id = uuid4()
    connection_id = await _connection(stranger_id, allow_non_interactive=True)
    trigger_id = await make_trigger(connection_id=connection_id)

    await _append(trigger_id)
    assert await dispatcher.run_once(owner="solo") == 0
    assert fake_background_service.submits == []


async def _append(trigger_id):
    async with session_scope() as session:
        event, _ = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key=f"e-{uuid4().hex[:8]}")
        return event.id
