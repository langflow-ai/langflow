"""LE-1776 item 1 — the summary must describe the flow that is actually delivered.

The agent writes its summary BEFORE pre-delivery verification runs. When
verification repairs a flow, the fix turn rebuilds the canvas, and on success the
turn used to report ``verified: True`` without touching the text — so the user
read a confident description of the flow the agent originally produced next to a
card containing a different one, above a destructive "Replace canvas" button.

Reproduces QA's case: "add a Loop component but don't connect anything to it"
delivered a 5-node working loop under the summary "an unconnected Loop component".
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.agentic.services.assistant_service import execute_flow_with_validation_streaming
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"
FLOW_ID = "11111111-1111-1111-1111-111111111111"


def _intent(intent="build_flow"):
    return IntentResult(intent=intent, translation="build a flow")


def _stream_end(text):
    def _make(**_kwargs):
        async def gen():
            yield "end", {"result": text}

        return gen()

    return _make


def _drain_set_flow_once():
    state = {"done": False}

    def _drain():
        if state["done"]:
            return []
        state["done"] = True
        return [{"action": "set_flow"}]

    return _drain


def _node(node_id: str, node_type: str) -> dict:
    return {"id": node_id, "data": {"id": node_id, "type": node_type, "node": {"template": {}}}}


# What the user asked for: one component, nothing connected.
AS_REQUESTED = {"name": "f", "data": {"nodes": [_node("LoopComponent-1", "LoopComponent")], "edges": []}}

# What verification's fix turn rebuilt it into.
AFTER_REPAIR = {
    "name": "Working Loop Flow",
    "data": {
        "nodes": [
            _node("ChatInput-1", "ChatInput"),
            _node("LoopComponent-1", "LoopComponent"),
            _node("ParserComponent-1", "ParserComponent"),
            _node("Agent-1", "Agent"),
            _node("ChatOutput-1", "ChatOutput"),
        ],
        "edges": [
            {"source": "ChatInput-1", "target": "LoopComponent-1"},
            {"source": "LoopComponent-1", "target": "ParserComponent-1"},
            {"source": "ParserComponent-1", "target": "Agent-1"},
            {"source": "Agent-1", "target": "LoopComponent-1"},
            {"source": "LoopComponent-1", "target": "ChatOutput-1"},
        ],
    },
}

SUMMARY = "Built and proposed an unconnected Loop component; review and add it to the canvas."


def _complete_payload(events):
    for event in events:
        if '"event": "complete"' in event:
            return json.loads(event.split("data: ", 1)[1])
    return None


async def _collect(gen):
    return [event async for event in gen]


async def _run_turn(*, working_flows, run_results):
    """Drive one build turn. ``working_flows``/``run_results`` are call sequences."""
    run = AsyncMock(side_effect=run_results)
    with (
        patch(f"{MODULE}.classify_intent", AsyncMock(return_value=_intent())),
        patch(f"{MODULE}.execute_flow_file_streaming", MagicMock(side_effect=_stream_end(SUMMARY))),
        patch(f"{MODULE}.execute_flow_file", AsyncMock()),
        patch(f"{MODULE}.drain_flow_events", side_effect=_drain_set_flow_once()),
        patch(f"{MODULE}.extract_response_text", return_value=SUMMARY),
        patch(f"{MODULE}.get_working_flow", side_effect=working_flows),
        patch(f"{MODULE}.run_working_flow", run),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        return await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="flow_builder_assistant",
                input_value="add a Loop component but don't connect anything to it",
                global_variables={"FLOW_ID": FLOW_ID},
                max_retries=1,
            )
        )


class TestVerificationRebuildIsDisclosed:
    @pytest.mark.asyncio
    async def test_should_disclose_when_the_fix_turn_rebuilt_the_flow(self):
        """The delivered text must not keep describing the pre-repair flow."""
        events = await _run_turn(
            # pre-verification read, then the fix turn's read-back, then delivery reads
            working_flows=[AS_REQUESTED, AFTER_REPAIR, AFTER_REPAIR, AFTER_REPAIR, AFTER_REPAIR],
            run_results=[
                {"error": "No loop item data or processing instructions were provided."},
                {"result": "ok", "metrics": {}},
            ],
        )

        data = _complete_payload(events)
        assert data is not None
        text = data["data"]["result"]

        assert text != SUMMARY, "summary was delivered unchanged next to a different flow"
        assert data["data"].get("verification_rebuilt") is True
        lowered = text.lower()
        assert "adjust" in lowered or "changed" in lowered, f"no disclosure in: {text!r}"

    @pytest.mark.asyncio
    async def test_disclosure_states_the_delivered_shape(self):
        """Naming the real counts is what lets the user spot the contradiction."""
        events = await _run_turn(
            working_flows=[AS_REQUESTED, AFTER_REPAIR, AFTER_REPAIR, AFTER_REPAIR, AFTER_REPAIR],
            run_results=[
                {"error": "No loop item data or processing instructions were provided."},
                {"result": "ok", "metrics": {}},
            ],
        )

        text = _complete_payload(events)["data"]["result"]

        assert "5" in text, f"delivered node count missing from: {text!r}"
        assert SUMMARY in text, "the original summary must be preserved, not replaced"


class TestNoDisclosureWhenNothingChanged:
    """Non-regression: the untouched-flow path must stay byte-identical."""

    @pytest.mark.asyncio
    async def test_should_not_add_a_notice_when_verification_passed_first_try(self):
        events = await _run_turn(
            working_flows=[AS_REQUESTED, AS_REQUESTED, AS_REQUESTED, AS_REQUESTED],
            run_results=[{"result": "ok", "metrics": {}}],
        )

        data = _complete_payload(events)
        assert data["data"]["result"] == SUMMARY
        assert data["data"].get("verified") is True
        assert "verification_rebuilt" not in data["data"]
