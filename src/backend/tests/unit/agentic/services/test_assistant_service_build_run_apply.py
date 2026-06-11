"""End-to-end (generator-level) guard: build+run ALWAYS lands on the canvas.

The recurring "ele diz que fez e não fez" bug: user asks to build a flow
AND run it; the agent builds (``set_flow``) and runs it (``flow_ran``),
reports the result, but the canvas shows only a proposal card — the flow
was never applied. Old root cause: auto-apply was gated on a regex over
the user's wording (``_looks_like_run_request``) that misses "rode ele",
"run it", and every paraphrase/language.

These drive the REAL streaming generator with simulated tool-event
batches and assert the deterministic invariant for every ordering:
when the agent built AND ran the flow this turn, the stream MUST yield a
``set_flow`` with ``auto_apply: true`` and MUST NOT emit the
``flow_proposal_ready`` gate — regardless of the prompt text. Regression
cases (build-only, compound, run-only, incremental) are pinned too.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.assistant_service import execute_flow_with_validation_streaming
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"

SET_FLOW = {"action": "set_flow", "flow": {"data": {"nodes": [{"id": "Sum-1"}], "edges": []}}}
FLOW_RAN = {"action": "flow_ran", "flow_id": "f-1"}


def _intent(intent: str) -> IntentResult:
    return IntentResult(intent=intent, translation="t")


async def _collect(agen):
    return [e async for e in agen]


def _two_token_stream(**_kw):
    """A stream that triggers two live drains (token, token) then a final drain."""

    async def gen():
        yield "token", "Criei o flow..."
        yield "token", "...e rodei: sum_result 12.0"
        yield "end", {"result": "Criei e rodei no canvas. sum_result: 12.0"}

    return gen()


def _one_token_stream(**_kw):
    async def gen():
        yield "token", "Done."
        yield "end", {"result": "Built and ran it."}

    return gen()


def _has_auto_applied_set_flow(events: list[str]) -> bool:
    return any('"action": "set_flow"' in e and '"auto_apply": true' in e for e in events)


def _has_proposal_gate(events: list[str]) -> bool:
    return any('"step": "flow_proposal_ready"' in e for e in events)


async def _run_generator(*, input_value: str, intent: str, drain_batches: list[list[dict]], stream):
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent(intent)),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=stream),
        patch(f"{MODULE}.drain_flow_events", side_effect=list(drain_batches)),
        patch(f"{MODULE}.reset_working_flow"),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        return await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value=input_value,
                global_variables={},
                max_retries=1,
            )
        )


class TestBuildAndRunAlwaysApplies:
    """The core invariant — for every event ordering and any wording."""

    @pytest.mark.asyncio
    async def test_set_flow_and_flow_ran_same_batch_auto_applies_no_gate(self):
        events = await _run_generator(
            input_value="crie um flow e rode ele",
            intent="build_flow",
            drain_batches=[[dict(SET_FLOW), dict(FLOW_RAN)], [], []],
            stream=_one_token_stream,
        )
        assert _has_auto_applied_set_flow(events), f"build+run must apply to canvas. {events}"
        assert not _has_proposal_gate(events), "applied flow must NOT show the proposal gate"
        assert not any('"action": "flow_ran"' in e for e in events), "flow_ran is internal-only"
        assert any('"event": "complete"' in e for e in events)

    @pytest.mark.asyncio
    async def test_set_flow_then_run_in_later_batch_reapplies(self):
        # Tokens stream BETWEEN build_flow and run_flow → set_flow is drained
        # (and proposed) before flow_ran is known. Must still end applied.
        # 4 drain batches: one per token (2), one post-stream, one in the
        # post-verification fix-turn drain.
        events = await _run_generator(
            input_value="crie um flow e rode ele",
            intent="build_flow",
            drain_batches=[[dict(SET_FLOW)], [dict(FLOW_RAN)], [], []],
            stream=_two_token_stream,
        )
        assert _has_auto_applied_set_flow(events), f"late run must re-apply the proposed flow to the canvas. {events}"
        assert not _has_proposal_gate(events)

    @pytest.mark.asyncio
    async def test_decision_is_wording_agnostic_even_when_run_regex_misses(self):
        # Force the legacy run-wording regex to MISS (the real failing case:
        # "rode ele" has no "flow/fluxo"). The flow_ran action alone must
        # still cause the canvas application — proving LLM/language-agnostic.
        with patch(f"{MODULE}._looks_like_run_request", return_value=False):
            events = await _run_generator(
                input_value="coloque no canvas e rode ele",
                intent="build_flow",
                drain_batches=[[dict(SET_FLOW), dict(FLOW_RAN)], [], []],
                stream=_one_token_stream,
            )
        assert _has_auto_applied_set_flow(events), (
            f"build+run must apply even when the prompt-wording regex misses. {events}"
        )
        assert not _has_proposal_gate(events)


class TestNoRegression:
    @pytest.mark.asyncio
    async def test_build_only_no_run_stays_a_gated_proposal(self):
        events = await _run_generator(
            input_value="crie um flow de chatbot",
            intent="build_flow",
            drain_batches=[[dict(SET_FLOW)], [], []],
            stream=_one_token_stream,
        )
        assert not _has_auto_applied_set_flow(events), "build-only must remain a proposal"
        assert _has_proposal_gate(events), "build-only must keep the Continue/Dismiss gate"
        assert any('"event": "complete"' in e for e in events)

    @pytest.mark.asyncio
    async def test_compound_still_auto_applies(self):
        events = await _run_generator(
            input_value="crie um componente e um flow com ele",
            intent="component_then_flow",
            drain_batches=[[dict(SET_FLOW)], [], []],
            stream=_one_token_stream,
        )
        assert _has_auto_applied_set_flow(events), "compound must keep auto-applying (no regression)"
        assert not _has_proposal_gate(events)

    @pytest.mark.asyncio
    async def test_build_only_then_no_run_never_double_emits(self):
        events = await _run_generator(
            input_value="crie um flow de chatbot",
            intent="build_flow",
            drain_batches=[[dict(SET_FLOW)], [], []],
            stream=_one_token_stream,
        )
        set_flow_events = [e for e in events if '"action": "set_flow"' in e]
        assert len(set_flow_events) == 1, f"set_flow must be emitted exactly once. {set_flow_events}"
