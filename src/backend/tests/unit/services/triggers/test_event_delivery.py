"""The firing event actually reaches the flow.

This is the seam nothing else covers end to end: the dispatcher builds a run
request, the worker re-parses it, the tweaks land on the trigger node's template
before the graph is built, and the component reads its event back out. Each half
has its own tests; only together do they prove a schedule tick becomes an event
a downstream agent can see.

The pieces are the real ones — the shipped component template, the real
``WorkflowRunRequest`` parse, the real ``process_tweaks`` — so a change to any of
them that quietly stops delivering the event fails here rather than in
production.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.triggers import dispatcher
from langflow.services.triggers.constants import TRIGGER_EVENT_FIELD
from lfx.base.triggers.base import TRIGGER_EVENT_FIELD as LFX_TRIGGER_EVENT_FIELD
from lfx.components.triggers import ScheduleTriggerComponent
from lfx.processing.process import process_tweaks

pytestmark = pytest.mark.no_blockbuster

NODE_ID = "ScheduleTrigger-e2e01"


def test_trigger_event_field_matches_the_lfx_component_contract() -> None:
    """One string, declared twice: lfx must not import langflow.

    The dispatcher tweaks by this name and the component reads by this name. If
    the two drift, every trigger fires into a flow that sees nothing, and no
    other test notices because each side is self-consistent.
    """
    assert TRIGGER_EVENT_FIELD == LFX_TRIGGER_EVENT_FIELD


def _canvas() -> dict:
    """A one-node canvas carrying the trigger component's real template."""
    frontend_node = ScheduleTriggerComponent().to_frontend_node()
    node = frontend_node.get("data", frontend_node)
    return {
        "nodes": [{"id": NODE_ID, "data": {"type": "ScheduleTrigger", "id": NODE_ID, "node": node["node"]}}],
        "edges": [],
    }


def test_a_dispatched_event_arrives_on_the_trigger_node_and_is_read_back() -> None:
    from langflow.api.v2.workflow import _parse_persisted_workflow_request

    trigger = Trigger(
        flow_id=uuid4(),
        user_id=uuid4(),
        name="digest",
        kind="schedule",
        node_id=NODE_ID,
        config={"cron": "0 8 * * 1-5", "timezone": "Europe/Lisbon"},
        provider_state={},
        concurrency_limit=1,
        max_attempts=5,
    )
    event = TriggerEvent(
        trigger_id=trigger.id,
        dedupe_key="tick:2026-09-07T08:00:00+00:00",
        payload={"scheduled_at": "2026-09-07T08:00:00+00:00", "missed_ticks": []},
    )

    # 1. The dispatcher's request, as the worker re-parses it.
    parsed = _parse_persisted_workflow_request(
        dispatcher.build_submit_request(trigger=trigger, event=event, binding_data=None)
    )

    # 2. The tweak applied to the real canvas, by the real tweak machinery.
    graph_data = process_tweaks(_canvas(), parsed.tweaks, stream=False)
    template = graph_data["nodes"][0]["data"]["node"]["template"]
    assert TRIGGER_EVENT_FIELD in template, "the trigger component must declare the field the dispatcher tweaks"

    # 3. The component reading its event back out of that template.
    component = ScheduleTriggerComponent()
    component.set_attributes({name: field.get("value") for name, field in template.items() if isinstance(field, dict)})
    delivered = component.build_event().data

    assert delivered["event_id"] == str(event.id)
    assert delivered["kind"] == "schedule"
    assert delivered["dedupe_key"] == "tick:2026-09-07T08:00:00+00:00"
    assert delivered["payload"]["scheduled_at"] == "2026-09-07T08:00:00+00:00"
    # And the value on the wire really is the JSON string the dispatcher wrote.
    assert json.loads(template[TRIGGER_EVENT_FIELD]["value"])["event_id"] == str(event.id)


def test_a_run_nobody_triggered_leaves_the_node_empty() -> None:
    """A canvas Play must not fail on a flow that happens to hold a trigger."""
    graph_data = process_tweaks(_canvas(), {}, stream=False)
    template = graph_data["nodes"][0]["data"]["node"]["template"]

    component = ScheduleTriggerComponent()
    component.set_attributes({name: field.get("value") for name, field in template.items() if isinstance(field, dict)})

    assert component.build_event().data == {}
    assert "No trigger event" in component.status
