"""Headless callers apply edits live and are steered away from review wording.

Bug #13641: driven headlessly via the MCP ``run_assistant`` tool, a text
``configure`` on a pre-existing node was surfaced as an ``edit_field`` review
proposal — never written to the working flow (no UI to approve it) and narrated
as "(pending user approval)".

The streaming entrypoint takes ``apply_edits_immediately``. When set it:
  1. flips the lfx ``set_apply_edits_live`` switch so the propose tools apply
     the change live instead of queuing a review card, and
  2. injects a headless directive into the agent input so the LLM reports the
     edit as DONE rather than proposed.

These drive the REAL streaming generator and assert both wirings for a flow turn.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.assistant_service import execute_flow_with_validation_streaming
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"


def _intent(intent: str) -> IntentResult:
    return IntentResult(intent=intent, translation="t")


async def _collect(agen):
    return [e async for e in agen]


async def _run(*, apply_edits_immediately: bool) -> tuple[list[bool], str]:
    """Run a flow-edit turn; return (apply_live_calls, agent_input_value)."""
    apply_live_calls: list[bool] = []
    captured: dict[str, str] = {}

    def _spy_live(*, enabled: bool) -> None:
        apply_live_calls.append(enabled)

    def _agent_stream(*_args, **kwargs):
        # The first call is the real turn; a no-action retry may follow with a
        # different template, so only the first input carries the directive.
        captured.setdefault("input_value", kwargs.get("input_value", ""))

        async def gen():
            yield "end", {"result": "Updated the system prompt."}

        return gen()

    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=_agent_stream),
        patch(f"{MODULE}.drain_flow_events", return_value=[]),
        patch(f"{MODULE}.reset_working_flow"),
        patch(f"{MODULE}.set_apply_edits_live", side_effect=_spy_live),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="Set the Agent's system prompt to exactly 'X'.",
                global_variables={},
                max_retries=1,
                apply_edits_immediately=apply_edits_immediately,
            )
        )
    return apply_live_calls, captured.get("input_value", "")


class TestHeadlessAppliesEditsLive:
    @pytest.mark.asyncio
    async def test_should_enable_live_apply_and_inject_directive_when_headless(self):
        calls, agent_input = await _run(apply_edits_immediately=True)
        assert calls, "set_apply_edits_live must be called for a flow turn"
        assert calls[-1] is True, f"set_apply_edits_live must be enabled headlessly; got {calls}"
        assert "Headless session" in agent_input, agent_input
        assert "applied" in agent_input.lower()

    @pytest.mark.asyncio
    async def test_should_not_enable_live_apply_nor_inject_directive_in_ui_path(self):
        calls, agent_input = await _run(apply_edits_immediately=False)
        assert calls, "set_apply_edits_live must be called for a flow turn"
        assert calls[-1] is False, f"UI path must leave live-apply off; got {calls}"
        assert "Headless session" not in agent_input
