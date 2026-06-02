"""Slice 4 — post-build flow verification wired into the live turn.

Characterization first (the no-FLOW_ID path must stay byte-identical),
then the new behavior: a built flow whose real run fails with a
non-fixable error is delivered with an honest caveat — never as a
confident success — and the kill switch restores legacy behavior.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.agentic.services.assistant_service import execute_flow_with_validation_streaming
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"


def _intent(intent):
    return IntentResult(intent=intent, translation="build a flow")


def _stream_end():
    async def gen():
        yield "end", {"result": "Flow built."}

    return gen()


def _drain_set_flow_once():
    """drain_flow_events: emit one set_flow on the first call, then []."""
    state = {"done": False}

    def _drain():
        if state["done"]:
            return []
        state["done"] = True
        return [{"action": "set_flow"}]

    return _drain


_BUILT_FLOW = {
    "name": "f",
    "data": {
        "nodes": [
            {"id": "ChatInput-1", "data": {"type": "ChatInput", "node": {"template": {"input_value": {"value": ""}}}}},
            {"id": "ChatOutput-1", "data": {"type": "ChatOutput", "node": {"template": {}}}},
        ],
        "edges": [{"source": "ChatInput-1", "target": "ChatOutput-1"}],
    },
}


def _complete_payload(events):
    for e in events:
        if '"event": "complete"' in e:
            return json.loads(e.split("data: ", 1)[1])
    return None


async def _collect(gen):
    return [e async for e in gen]


class TestCharacterizationNoFlowIdPath:
    """SAFETY NET: with no FLOW_ID, the build path is unchanged by Slice 4."""

    @pytest.mark.asyncio
    async def test_should_emit_flow_proposal_ready_then_one_complete_without_caveat(self):
        with (
            patch(f"{MODULE}.classify_intent", AsyncMock(return_value=_intent("build_flow"))),
            patch(f"{MODULE}.execute_flow_file_streaming", MagicMock(side_effect=lambda **_k: _stream_end())),
            patch(f"{MODULE}.drain_flow_events", side_effect=_drain_set_flow_once()),
            patch(f"{MODULE}.extract_response_text", return_value="Flow built."),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect(
                execute_flow_with_validation_streaming(
                    flow_filename="flow_builder_assistant",
                    input_value="build me a chat flow",
                    global_variables={},  # NO FLOW_ID → verification must not trigger
                    max_retries=1,
                )
            )

        blob = "\n".join(events)
        assert '"step": "flow_proposal_ready"' in blob
        assert len([e for e in events if '"event": "complete"' in e]) == 1
        assert '"event": "error"' not in blob
        assert "verification_caveat" not in blob


class TestFlowVerificationDeliversHonestCaveat:
    @pytest.mark.asyncio
    async def test_should_deliver_caveat_when_built_flow_run_fails_non_fixably(self):
        run = AsyncMock(return_value={"error": "Incorrect API key provided"})
        with (
            patch(f"{MODULE}.classify_intent", AsyncMock(return_value=_intent("build_flow"))),
            patch(f"{MODULE}.execute_flow_file_streaming", MagicMock(side_effect=lambda **_k: _stream_end())),
            patch(f"{MODULE}.drain_flow_events", side_effect=_drain_set_flow_once()),
            patch(f"{MODULE}.extract_response_text", return_value="Flow built."),
            patch(f"{MODULE}.get_working_flow", return_value=_BUILT_FLOW),
            patch(f"{MODULE}.run_working_flow", run),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect(
                execute_flow_with_validation_streaming(
                    flow_filename="flow_builder_assistant",
                    input_value="build me a chat flow",
                    global_variables={"FLOW_ID": "11111111-1111-1111-1111-111111111111"},
                    max_retries=1,
                )
            )

        run.assert_awaited()  # the flow was actually run to verify it
        blob = "\n".join(events)
        assert '"event": "error"' not in blob  # flow still delivered, not an error
        data = _complete_payload(events)
        assert data is not None
        # Honest: presented with a caveat, NOT as a confident success.
        assert data["data"].get("verified") is False
        assert data["data"].get("verification_caveat")
        assert "couldn't" in data["data"]["verification_caveat"].lower()

    @pytest.mark.asyncio
    async def test_kill_switch_disables_verification(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_ASSISTANT_VERIFY_FLOWS", "0")
        run = AsyncMock()
        with (
            patch(f"{MODULE}.classify_intent", AsyncMock(return_value=_intent("build_flow"))),
            patch(f"{MODULE}.execute_flow_file_streaming", MagicMock(side_effect=lambda **_k: _stream_end())),
            patch(f"{MODULE}.drain_flow_events", side_effect=_drain_set_flow_once()),
            patch(f"{MODULE}.extract_response_text", return_value="Flow built."),
            patch(f"{MODULE}.get_working_flow", return_value=_BUILT_FLOW),
            patch(f"{MODULE}.run_working_flow", run),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect(
                execute_flow_with_validation_streaming(
                    flow_filename="flow_builder_assistant",
                    input_value="build me a chat flow",
                    global_variables={"FLOW_ID": "11111111-1111-1111-1111-111111111111"},
                    max_retries=1,
                )
            )

        run.assert_not_called()  # kill switch → no verification run
        assert "verification_caveat" not in "\n".join(events)
