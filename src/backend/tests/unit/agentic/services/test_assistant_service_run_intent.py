"""Bugfix — a run-flow request must NOT plan-gate nor trip the WS-2 no-action build guard.

Repro (user logs): "rode o flow e me diga o resultado" was classified
build_flow → "Generating plan…" → the agent ran the flow and got "woof",
but running emits ``run_update`` (not ``flow_update``) so has_flow_updates
stayed False and the no-action guard fired, replacing the real result
with "I couldn't apply that change to the canvas".
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"


def _intent(intent: str) -> IntentResult:
    return IntentResult(intent=intent, translation="run the flow")


def _gen(events):
    async def g():
        for et, ed in events:
            yield et, ed

    return g()


async def _collect(agen):
    return [e async for e in agen]


@pytest.mark.asyncio
async def test_run_flow_intent_routes_to_flow_builder_without_plan_gate():
    captured: dict = {}

    def streaming_factory(**kw):
        captured.update(kw)
        return _gen([("token", "running"), ("end", {"result": "The flow returned woof."})])

    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("run_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=streaming_factory),
        patch(f"{MODULE}.drain_flow_events", return_value=[]),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="rode o flow e me diga o resultado",
                global_variables={},
            )
        )

    assert captured["flow_filename"].startswith("flow_builder_assistant"), captured["flow_filename"]
    # No planning step for a pure run.
    assert not any('"generating_plan"' in e for e in events), f"run must not plan-gate. {events}"


@pytest.mark.asyncio
async def test_run_flow_intent_does_not_trip_no_action_guard():
    """The core bug: a successful run must surface its result, not the 'couldn't apply' error."""
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("run_flow")),
        patch(
            f"{MODULE}.execute_flow_file_streaming",
            return_value=_gen([("end", {"result": "The flow returned woof."})]),
        ),
        patch(f"{MODULE}.drain_flow_events", return_value=[]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="rode o flow e me diga o resultado",
                global_variables={},
                max_retries=1,
            )
        )

    assert any('"event": "complete"' in e for e in events), f"run result must complete. {events}"
    assert not any('"event": "error"' in e for e in events), (
        f"run must NOT emit the no-action build error. Events: {events}"
    )


@pytest.mark.asyncio
async def test_flow_request_does_not_show_false_planning_label():
    """No false PLANNING *message* for a possibly-direct edit.

    User bug: the frontend showed "Generating plan..." (PLANNING) but the
    agent then changed the value directly with no plan card. The backend
    cannot know BUILD-vs-EDIT at label time, so it must NOT emit the
    misleading ``generating_plan`` step nor a "Generating plan..."
    message. UX requirement change: the STEP is now the rich
    ``generating_flow`` (so the frontend renders the flow icon/card
    immediately, parity with ``generating_component``) but the MESSAGE
    stays NEUTRAL ("Working on the flow...") — step != message.
    """
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(
            f"{MODULE}.execute_flow_file_streaming",
            return_value=_gen([("end", {"result": "Set input_value to 'Dog'."})]),
        ),
        patch(f"{MODULE}.drain_flow_events", return_value=[{"action": "configure"}]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="mude o input para Dog",
                global_variables={},
                max_retries=1,
            )
        )

    assert not any('"generating_plan"' in e for e in events), (
        f"must not emit the misleading PLANNING step for a possibly-direct edit. {events}"
    )
    # The rich `generating_flow` step IS used (icon/card parity with
    # generating_component) — but the message must NOT promise planning.
    assert any('"step": "generating_flow"' in e for e in events), (
        f"the rich generating_flow step must be emitted. {events}"
    )
    assert not any("Generating plan" in e for e in events), (
        f"must not show a false 'Generating plan...' message. {events}"
    )


@pytest.mark.asyncio
async def test_complete_flags_continuation_expected_for_edit_plus_run():
    """Continuation fires only when a deferred step was requested.

    The backend computes this deterministically from the original input
    (run-intent) and ships it on the complete event.
    """
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(
            f"{MODULE}.execute_flow_file_streaming",
            return_value=_gen([("end", {"result": "Proposed the edit."})]),
        ),
        patch(f"{MODULE}.drain_flow_events", return_value=[{"action": "edit_field"}]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="mude o input para Cat e rode o flow",
                global_variables={},
                max_retries=1,
            )
        )

    complete = next(e for e in events if '"event": "complete"' in e)
    assert '"continuation_expected": true' in complete, complete


@pytest.mark.asyncio
async def test_complete_does_not_flag_continuation_for_pure_edit():
    """A pure edit must NOT trigger a continuation turn.

    "melhore o agent instructions" (no run/test) produced the
    duplicate-message glitch when the continuation fired needlessly.
    """
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(
            f"{MODULE}.execute_flow_file_streaming",
            return_value=_gen([("end", {"result": "Proposed the edit."})]),
        ),
        patch(f"{MODULE}.drain_flow_events", return_value=[{"action": "edit_field"}]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="melhore o agent instructions",
                global_variables={},
                max_retries=1,
            )
        )

    complete = next(e for e in events if '"event": "complete"' in e)
    assert '"continuation_expected": false' in complete, complete


@pytest.mark.asyncio
async def test_compound_request_emits_orchestrating_step():
    """Compound (multi-ask) request emits a dedicated 'orchestrating' step.

    So the frontend shows a real indicator instead of a generic
    'Thinking...'.
    """
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("component_then_flow")),
        patch(
            f"{MODULE}.execute_flow_file_streaming",
            return_value=_gen([("end", {"result": "done"})]),
        ),
        patch(f"{MODULE}.drain_flow_events", return_value=[{"action": "set_flow"}]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a prime component, build a flow with it and run it with 14",
                global_variables={},
                max_retries=1,
            )
        )

    assert any('"step": "orchestrating"' in e for e in events), f"compound must emit orchestrating. {events}"
    assert not any('"generating_plan"' in e for e in events), events


@pytest.mark.asyncio
async def test_build_flow_that_also_runs_emits_orchestrating_step():
    """build_flow + run in one prompt → 'orchestrating' indicator.

    A multi-step orchestration (build → configure → run), even though
    gpt-class models classify it build_flow (no custom component).
    """
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", return_value=_gen([("end", {"result": "done"})])),
        patch(f"{MODULE}.drain_flow_events", side_effect=[[{"action": "set_flow"}], [], []]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="quero que crie um flow com um agent e rode esse flow e me diga o resultado",
                global_variables={},
                max_retries=1,
            )
        )
    assert any('"step": "orchestrating"' in e for e in events), f"build+run must orchestrate. {events}"


@pytest.mark.asyncio
async def test_pure_build_without_run_does_not_emit_orchestrating():
    """Pure build (no run ask) keeps the neutral 'generating' step.

    Regression guard: it must NOT emit 'orchestrating'.
    """
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", return_value=_gen([("end", {"result": "done"})])),
        patch(f"{MODULE}.drain_flow_events", side_effect=[[{"action": "set_flow"}], [], []]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a chatbot flow with an agent",
                global_variables={},
                max_retries=1,
            )
        )
    assert not any('"step": "orchestrating"' in e for e in events), events


@pytest.mark.asyncio
async def test_compound_set_flow_auto_applies_without_continue_gate():
    """Compound auto-applies the canvas — no Continue gate.

    The set_flow event carries auto_apply=True and NO flow_proposal_ready
    gate is emitted (the user already asked to clear+replace the canvas).
    """
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("component_then_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", return_value=_gen([("end", {"result": "done"})])),
        patch(f"{MODULE}.drain_flow_events", side_effect=[[{"action": "set_flow", "flow": {}}], [], []]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a prime component, build a flow with it and run it",
                global_variables={},
                max_retries=1,
            )
        )

    assert any('"auto_apply": true' in e for e in events), f"compound set_flow must auto-apply. {events}"
    assert not any('"flow_proposal_ready"' in e for e in events), f"compound must NOT gate. {events}"


@pytest.mark.asyncio
async def test_single_ask_build_flow_still_gates_and_does_not_auto_apply():
    """Single-ask build_flow keeps the Continue/Dismiss gate.

    Regression guard: a plain build_flow does NOT auto-apply (single-ask
    UX unchanged).
    """
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", return_value=_gen([("end", {"result": "done"})])),
        patch(f"{MODULE}.drain_flow_events", side_effect=[[{"action": "set_flow", "flow": {}}], [], []]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="build me a chatbot flow",
                global_variables={},
                max_retries=1,
            )
        )

    assert any('"flow_proposal_ready"' in e for e in events), f"single-ask build must gate. {events}"
    assert not any('"auto_apply": true' in e for e in events), f"single-ask must NOT auto-apply. {events}"


@pytest.mark.asyncio
async def test_available_model_hint_injected_when_provider_and_model_given():
    """Inject a key-backed model so any Agent built can run.

    Avoids "No model selected". Injected only when the request carries
    provider+model_name; absent otherwise (input byte-identical to before).
    """
    seen: list = []

    def factory(**kw):
        seen.append(kw["input_value"])
        return _gen([("end", {"result": "ok"})])

    # set_flow → completes on the first call (no no-action retry).
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=factory),
        patch(f"{MODULE}.drain_flow_events", side_effect=[[{"action": "set_flow", "flow": {}}], [], []]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="build an agent flow",
                global_variables={},
                provider="OpenAI",
                model_name="gpt-4o-mini",
                max_retries=1,
            )
        )
    assert "Available language models" in seen[0], seen[0]
    assert "OpenAI" in seen[0], seen[0]
    assert "gpt-4o-mini" in seen[0], seen[0]

    # No request provider, but a NON-OpenAI key configured → the block
    # lists that provider (provider-agnostic, no OpenAI obligation).
    seen.clear()
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=factory),
        patch(f"{MODULE}.drain_flow_events", side_effect=[[{"action": "set_flow", "flow": {}}], [], []]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="build an agent flow",
                global_variables={"ANTHROPIC_API_KEY": "sk-test"},
                max_retries=1,
            )
        )
    assert "providers with credentials configured: Anthropic" in seen[0], seen[0]

    # Nothing configured at all → no hint (regression-safe, byte-identical).
    seen.clear()
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=factory),
        patch(f"{MODULE}.drain_flow_events", side_effect=[[{"action": "set_flow", "flow": {}}], [], []]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="build an agent flow",
                global_variables={},
                max_retries=1,
            )
        )
    assert "Available language models" not in seen[0]


@pytest.mark.asyncio
async def test_build_flow_truly_no_action_still_guarded_regression():
    """Regression: a real build that did NOTHING (no flow updates, no run) must still be guarded."""
    with (
        patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_intent("build_flow")),
        patch(
            f"{MODULE}.execute_flow_file_streaming",
            return_value=_gen([("end", {"result": "I will add a node."})]),
        ),
        patch(f"{MODULE}.drain_flow_events", return_value=[]),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        events = await _collect(
            execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="add a chatinput",
                global_variables={},
                max_retries=1,
            )
        )

    assert any('"event": "error"' in e for e in events), f"a no-op build must still be guarded. Events: {events}"
