"""What a trigger fires, and which session the run joins."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.trigger.schemas import TriggerBindingTarget, TriggerSessionPolicy
from langflow.services.deps import session_scope
from langflow.services.triggers.binding import resolve_binding
from langflow.services.triggers.correlation import PAYLOAD_SESSION_KEY, derive_session_id
from langflow.services.triggers.errors import BindingUnsupportedError

pytestmark = pytest.mark.no_blockbuster


async def test_an_unpinned_trigger_runs_the_saved_flow(make_trigger) -> None:
    trigger_id = await make_trigger()
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        binding = await resolve_binding(session, trigger)
    assert binding.is_pinned is False
    assert binding.data is None
    assert binding.flow_id == trigger.flow_id


async def test_a_pinned_trigger_carries_the_pinned_canvas(make_trigger) -> None:
    trigger_id = await make_trigger()
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        version = FlowVersion(
            flow_id=trigger.flow_id, user_id=trigger.user_id, data={"nodes": ["v3"]}, version_number=3
        )
        session.add(version)
        await session.flush()
        trigger.flow_version_id = version.id
        session.add(trigger)
        binding = await resolve_binding(session, trigger)
    assert binding.is_pinned is True
    assert binding.data == {"nodes": ["v3"]}


async def test_a_pin_to_another_flows_version_is_refused(make_trigger, trigger_owner) -> None:
    """A dangling or cross-flow pin must not degrade into "run the current flow"."""
    trigger_id = await make_trigger()
    async with session_scope() as session:
        other_flow = Flow(name=f"other-{uuid4().hex[:6]}", user_id=trigger_owner)
        session.add(other_flow)
        await session.flush()
        foreign = FlowVersion(flow_id=other_flow.id, user_id=trigger_owner, data={"nodes": []}, version_number=1)
        session.add(foreign)
        await session.flush()
        trigger = await session.get(Trigger, trigger_id)
        trigger.flow_version_id = foreign.id
        session.add(trigger)
        with pytest.raises(BindingUnsupportedError):
            await resolve_binding(session, trigger)


async def test_a_missing_pin_is_refused(make_trigger) -> None:
    trigger_id = await make_trigger()
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.flow_version_id = uuid4()
        with pytest.raises(BindingUnsupportedError):
            await resolve_binding(session, trigger)


async def test_a_deployment_binding_is_typed_not_silently_rewritten(make_trigger) -> None:
    trigger_id = await make_trigger(binding_target=TriggerBindingTarget.DEPLOYMENT.value)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        with pytest.raises(BindingUnsupportedError) as excinfo:
            await resolve_binding(session, trigger)
    assert excinfo.value.target == TriggerBindingTarget.DEPLOYMENT.value


def _event(trigger_id, payload: dict | None = None) -> TriggerEvent:
    return TriggerEvent(id=uuid4(), trigger_id=trigger_id, dedupe_key="k", payload=payload or {})


def _trigger(**overrides) -> Trigger:
    fields = {
        "id": uuid4(),
        "flow_id": uuid4(),
        "user_id": uuid4(),
        "name": "t",
        "kind": "schedule",
        "config": {},
        "provider_state": {},
        "concurrency_limit": 1,
        "max_attempts": 3,
        "session_policy": TriggerSessionPolicy.PER_EVENT.value,
    }
    fields.update(overrides)
    return Trigger(**fields)


def test_two_events_from_one_conversation_share_a_session() -> None:
    """The agent-memory story: one provider thread, one session, two runs."""
    trigger = _trigger()
    conversation = {PAYLOAD_SESSION_KEY: "slack:T1:C1:1725500000.1"}
    first = derive_session_id(trigger, _event(trigger.id, conversation))
    second = derive_session_id(trigger, _event(trigger.id, dict(conversation)))
    assert first == second == "slack:T1:C1:1725500000.1"


def test_two_events_from_different_conversations_do_not_share_a_session() -> None:
    trigger = _trigger()
    first = derive_session_id(trigger, _event(trigger.id, {PAYLOAD_SESSION_KEY: "slack:T1:C1:1"}))
    second = derive_session_id(trigger, _event(trigger.id, {PAYLOAD_SESSION_KEY: "slack:T1:C2:1"}))
    assert first != second


def test_a_schedule_gets_a_fresh_session_per_tick_by_default() -> None:
    """A schedule has no conversation, so ticks are independent unless asked otherwise."""
    trigger = _trigger()
    first = derive_session_id(trigger, _event(trigger.id))
    second = derive_session_id(trigger, _event(trigger.id))
    assert first != second
    assert first.startswith(f"trigger:{trigger.id}:")


def test_a_shared_session_policy_keeps_one_session_across_ticks() -> None:
    trigger = _trigger(session_policy=TriggerSessionPolicy.SHARED.value)
    first = derive_session_id(trigger, _event(trigger.id))
    second = derive_session_id(trigger, _event(trigger.id))
    assert first == second == f"trigger:{trigger.id}"


def test_a_blank_provider_key_falls_back_to_the_trigger_policy() -> None:
    """A provider that sends an empty conversation id must not collapse sessions."""
    trigger = _trigger(session_policy=TriggerSessionPolicy.SHARED.value)
    assert derive_session_id(trigger, _event(trigger.id, {PAYLOAD_SESSION_KEY: "   "})) == f"trigger:{trigger.id}"
    assert derive_session_id(trigger, _event(trigger.id, {PAYLOAD_SESSION_KEY: ""})) == f"trigger:{trigger.id}"
