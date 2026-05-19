"""Tests for assistant service streaming with validation.

Tests the execute_flow_with_validation_streaming function,
including intent classification, code extraction, validation,
retry logic, and cancellation handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"


def _make_intent(intent="question", translation="test"):
    return IntentResult(intent=intent, translation=translation)


def _make_flow_events(events):
    """Create an async generator factory from a list of (type, data) tuples."""

    async def gen():
        for event_type, event_data in events:
            yield event_type, event_data

    return gen


async def _collect_events(gen):
    """Collect all SSE events from an async generator."""
    return [event async for event in gen]


class TestIntentClassificationCall:
    """Tests that classify_intent is called correctly."""

    @pytest.mark.asyncio
    async def test_should_call_classify_intent_without_session_id(self):
        """classify_intent should NOT receive session_id parameter."""
        mock_classify = AsyncMock(return_value=_make_intent())
        flow_gen = _make_flow_events([("end", {"result": "hi"})])

        with (
            patch(f"{MODULE}.classify_intent", mock_classify),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
                session_id="session-123",
                user_id="user-1",
            )
            await _collect_events(gen)

            call_kwargs = mock_classify.call_args[1]
            assert "session_id" not in call_kwargs

    @pytest.mark.asyncio
    async def test_should_pass_provider_and_model_to_classify_intent(self):
        """classify_intent should receive provider and model_name."""
        mock_classify = AsyncMock(return_value=_make_intent())
        flow_gen = _make_flow_events([("end", {"result": "hi"})])

        with (
            patch(f"{MODULE}.classify_intent", mock_classify),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
                provider="OpenAI",
                model_name="gpt-4",
                api_key_var="OPENAI_API_KEY",
            )
            await _collect_events(gen)

            call_kwargs = mock_classify.call_args[1]
            assert call_kwargs["provider"] == "OpenAI"
            assert call_kwargs["model_name"] == "gpt-4"
            assert call_kwargs["api_key_var"] == "OPENAI_API_KEY"


class TestQAResponse:
    """Tests for Q&A (non-component) responses."""

    @pytest.mark.asyncio
    async def test_should_return_plain_text_for_qa_without_code(self):
        """Q&A response without component code should return as plain text."""
        flow_gen = _make_flow_events(
            [
                ("token", "Hello "),
                ("token", "world!"),
                ("end", {"result": "Hello world!"}),
            ]
        )

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="what is langflow?",
                global_variables={},
            )
            events = await _collect_events(gen)

            # Should contain token events and a final complete event
            token_events = [e for e in events if "token" in e]
            final_complete = [e for e in events if '"event": "complete"' in e]
            assert len(token_events) >= 1
            assert len(final_complete) == 1

    @pytest.mark.asyncio
    async def test_should_return_plain_text_for_qa_with_component_code(self):
        """Q&A response containing component code should NOT trigger validation.

        When intent is "question", code extraction is skipped entirely to prevent
        example code in explanatory answers from being treated as component generation.
        """
        component_code = (
            "from langflow.custom import Component\n\n"
            "class MyComponent(Component):\n"
            "    description = 'test'\n"
            "    inputs = []\n"
        )

        response_text = f"Here's an example:\n\n```python\n{component_code}\n```\n\nHope that helps!"
        flow_gen = _make_flow_events([("end", {"result": response_text})])

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="how do I create a component?",
                global_variables={},
            )
            events = await _collect_events(gen)

            # Should NOT contain validation events — Q&A skips code extraction
            validation_events = [e for e in events if "extracting_code" in e or '"validating"' in e]
            assert len(validation_events) == 0

            # Should contain a complete event with the full text response
            complete_events = [e for e in events if '"event": "complete"' in e]
            assert len(complete_events) == 1

    @pytest.mark.asyncio
    async def test_should_return_plain_text_when_question_response_contains_example_code(self):
        """Q&A response with example component code should NOT trigger validation.

        Bug: User asks "how do I create a custom component?" and the LLM responds
        with an explanation plus an example code snippet. The fallback code extraction
        detects 'class SumComponent(Component)' in the example and triggers the
        validation pipeline, showing a component card instead of the text answer.
        """
        # Use a raw string with triple-backtick code block (real markdown)
        explanation_with_example = (
            "To create a custom component, you need to:\n\n"
            "1. Create a Python file\n"
            "2. Define a class\n\n"
            "```python\n"
            "from lfx.custom import Component\n"
            "from lfx.io import Output\n"
            "from lfx.schema import Data\n\n"
            "class SumComponent(Component):\n"
            "    display_name = 'Sum'\n"
            "    description = 'Adds two numbers'\n"
            "    inputs = []\n"
            "    outputs = [Output(name='result', display_name='Result', method='run')]\n\n"
            "    def run(self) -> Data:\n"
            "        return Data(data={'result': 42})\n"
            "```\n"
        )
        flow_gen = _make_flow_events([("end", {"result": explanation_with_example})])

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="how do I create a custom component?",
                global_variables={},
            )
            events = await _collect_events(gen)

            # Should NOT contain validation-related events (extracting_code, validating, validated)
            validation_events = [e for e in events if "extracting_code" in e or "validating" in e]
            assert len(validation_events) == 0, (
                f"Q&A response with example code should not trigger validation. "
                f"Got validation events: {validation_events}"
            )

            # Should contain a complete event with the full text (not component card)
            complete_events = [e for e in events if '"event": "complete"' in e]
            assert len(complete_events) == 1


class TestCompoundOrchestration:
    """Compound prompt → the SINGLE agent loop, no phase recursion.

    `component_then_flow` goes to the FlowBuilderAssistant (which has the
    generate_component tool). ONE agent turn owns the whole inline request and
    calls generate_component → search_components → build_flow → run_flow as
    tools. Single-intent requests keep their existing dedicated paths
    (covered by TestComponentGeneration / the build-flow tests).
    """

    @pytest.mark.asyncio
    async def test_compound_routes_to_single_agent_loop_no_phase_recursion(self):
        mock_stream = MagicMock(
            side_effect=lambda **_kw: _make_flow_events([("end", {"result": "14 is not prime."})])()
        )
        mock_classify = AsyncMock(return_value=_make_intent("component_then_flow"))

        with (
            patch(f"{MODULE}.classify_intent", mock_classify),
            patch(f"{MODULE}.execute_flow_file_streaming", mock_stream),
            # The agent's build emits set_flow (it used build_flow as a tool).
            patch(f"{MODULE}.drain_flow_events", side_effect=[[{"action": "set_flow"}], [], []]),
            patch(f"{MODULE}.extract_response_text", return_value="14 is not prime."),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect_events(
                execute_flow_with_validation_streaming(
                    flow_filename="TestFlow",
                    input_value="create a prime checker component then build a flow with it and run it with 14",
                    global_variables={},
                    max_retries=1,
                )
            )

        blob = "\n".join(events)
        # Routed to the single FlowBuilderAssistant loop — NOT the component
        # path, and NOT a second recursive turn.
        assert mock_stream.call_count == 1, blob[:800]
        assert mock_stream.call_args.kwargs["flow_filename"].startswith("flow_builder_assistant")
        # The compound request never went through component-code validation
        # (the agent owns component creation as a tool, in-loop).
        assert not any('"validated"' in e for e in events), blob[:800]
        completes = [e for e in events if '"event": "complete"' in e]
        assert len(completes) == 1, blob[:800]
        assert not any('"event": "error"' in e for e in events), blob[:800]


class TestBuildAndRunAutoApply:
    """A 'build a flow AND run it' request must auto-apply to the canvas.

    Bug: a non-compound build_flow that ALSO asks to run ("crie um flow
    ... e rode") emitted set_flow GATED behind the Continue card and the
    agent claimed "coloquei no canvas" — but the canvas stayed empty
    (only compound `component_then_flow` set auto_apply). Gating a flow
    the user explicitly asked to RUN is contradictory. Deterministic,
    from the user's intent — never the LLM's wording.
    """

    @pytest.mark.asyncio
    async def test_build_plus_run_sets_auto_apply_and_skips_the_continue_gate(self):
        mock_stream = MagicMock(side_effect=lambda **_kw: _make_flow_events([("end", {"result": "17 é primo."})])())
        mock_classify = AsyncMock(return_value=_make_intent("build_flow"))

        with (
            patch(f"{MODULE}.classify_intent", mock_classify),
            patch(f"{MODULE}.execute_flow_file_streaming", mock_stream),
            patch(f"{MODULE}.drain_flow_events", side_effect=[[{"action": "set_flow"}], [], []]),
            patch(f"{MODULE}.extract_response_text", return_value="17 é primo."),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect_events(
                execute_flow_with_validation_streaming(
                    flow_filename="flow_builder_assistant",
                    input_value="crie um flow com um agent que identifica primos e rode esse flow",
                    global_variables={},
                    max_retries=1,
                )
            )

        blob = "\n".join(events)
        set_flow_events = [e for e in events if '"action": "set_flow"' in e]
        assert set_flow_events, blob[:800]
        # The built flow is APPLIED, not proposed-and-gated.
        assert any('"auto_apply": true' in e for e in set_flow_events), blob[:800]
        assert not any('"step": "flow_proposal_ready"' in e for e in events), blob[:800]
        assert not any('"event": "error"' in e for e in events), blob[:800]


class TestComponentGeneration:
    """Tests for component generation flow."""

    @pytest.mark.asyncio
    async def test_should_emit_progress_events_on_successful_validation(self):
        """Should emit generating_component and validation progress events."""
        component_code = "class MyComp(Component): pass"
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.class_name = "MyComp"

        response_text = f"```python\n{component_code}\n```"
        flow_gen = _make_flow_events([("end", {"result": response_text})])

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("generate_component")),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_validation),
            patch(f"{MODULE}.validate_component_runtime", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
            )
            events = await _collect_events(gen)

            # Should have progress events for generation and validation steps
            progress_steps = [
                e
                for e in events
                if any(step in e for step in ["generating_component", "extracting_code", "validating", "validated"])
            ]
            assert len(progress_steps) >= 2

    @pytest.mark.asyncio
    async def test_should_retry_on_validation_failure(self):
        """Should retry with error context when validation fails."""
        component_code = "class BadComp(Component): pass"
        mock_fail = MagicMock()
        mock_fail.is_valid = False
        mock_fail.error = "Missing inputs"
        mock_fail.class_name = "BadComp"

        mock_success = MagicMock()
        mock_success.is_valid = True
        mock_success.class_name = "FixedComp"

        call_count = 0

        async def mock_streaming():
            nonlocal call_count
            call_count += 1
            yield "end", {"result": f"```python\n{component_code}\n```"}

        response_text = f"```python\n{component_code}\n```"

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("generate_component")),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", side_effect=[mock_fail, mock_success]),
            patch(f"{MODULE}.validate_component_runtime", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=2,
            )
            events = await _collect_events(gen)

            # Should have called flow twice (first attempt + one retry)
            assert call_count == 2

            # Should have retry-related events
            retry_events = [e for e in events if "retry" in e.lower() or "validation_failed" in e.lower()]
            assert len(retry_events) >= 1

    @pytest.mark.asyncio
    async def test_should_return_error_when_max_retries_exhausted(self):
        """Should return validation error when all retries fail."""
        component_code = "class BrokenComp(Component): pass"
        mock_fail = MagicMock()
        mock_fail.is_valid = False
        mock_fail.error = "Persistent error"
        mock_fail.class_name = "BrokenComp"

        async def mock_streaming():
            yield "end", {"result": f"```python\n{component_code}\n```"}

        response_text = f"```python\n{component_code}\n```"

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("generate_component")),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_fail),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=1,
            )
            events = await _collect_events(gen)

            # Final event should contain validated=False info
            complete_events = [e for e in events if "complete" in e.lower()]
            assert len(complete_events) >= 1


class TestCancellation:
    """Tests for client disconnect / cancellation handling."""

    @pytest.mark.asyncio
    async def test_should_emit_cancelled_event_on_disconnect(self):
        """Should emit cancelled event when client disconnects."""

        async def is_disconnected():
            return True

        with patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
                is_disconnected=is_disconnected,
            )
            events = await _collect_events(gen)

            cancelled_events = [e for e in events if "cancelled" in e.lower()]
            assert len(cancelled_events) >= 1


class TestErrorHandling:
    """Tests for error handling in flow execution."""

    @pytest.mark.asyncio
    async def test_should_emit_error_event_on_http_exception(self):
        """Should emit error event when flow execution raises HTTPException."""
        from fastapi import HTTPException

        async def mock_streaming():
            raise HTTPException(status_code=500, detail="Internal server error")
            yield  # makes this an async generator

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
            )
            events = await _collect_events(gen)

            error_events = [e for e in events if "error" in e.lower()]
            assert len(error_events) >= 1

    @pytest.mark.asyncio
    async def test_should_emit_complete_event_with_validated_false_when_all_attempts_raise(self):
        """Bug: exhausted retries should emit a complete event, not a bare error event.

        When every attempt fails at execution time (weak model keeps blowing up), the
        user should see the 'Component generation failed' card rendered by the frontend
        from a complete event with validated=False, not a bare error event.

        Before Bug A's fix: first failure returned immediately with format_error_event
        and the user saw the raw "An internal error occurred" line.
        After fix: the streaming service retries up to total_attempts and, when all
        attempts fail, emits a format_complete_event with validated=False so the
        frontend renders the failure card and the spec's "use a more capable model"
        message.
        """
        from fastapi import HTTPException

        def streaming_factory(**_kw):
            async def always_raises():
                raise HTTPException(
                    status_code=500,
                    detail="1 validation error for InputSchema\ninput_value\n  Input should be a valid string",
                )
                yield  # pragma: no cover — makes this an async generator

            return always_raises()

        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=_make_intent("generate_component"),
            ),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=streaming_factory),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=1,
            )
            events = await _collect_events(gen)

            # Final event must be a complete event with validated=false so the frontend
            # renders the failure card rather than a raw error line.
            complete_events = [e for e in events if '"event": "complete"' in e]
            assert complete_events, f"Expected a complete event after exhausted retries. Events: {events}"
            assert any('"validated": false' in e.lower() for e in complete_events), (
                f"Expected validated=false in final complete event. Events: {complete_events}"
            )

    @pytest.mark.asyncio
    async def test_should_retry_component_generation_when_flow_execution_raises(self):
        """Bug: weak models (e.g. llama3.2) emit malformed tool calls that blow up the flow.

        When intent=generate_component and execute_flow_file_streaming raises an
        HTTPException on the first attempt, the assistant should retry up to
        max_retries instead of bailing out immediately. Today the streaming service
        catches HTTPException and returns, so the user sees "An internal error occurred"
        with no retry — even though the spec defines automatic retry on failure.
        """
        from fastapi import HTTPException

        component_code = "class FixedComp(Component): pass"
        response_text = f"```python\n{component_code}\n```"

        mock_success = MagicMock()
        mock_success.is_valid = True
        mock_success.class_name = "FixedComp"

        call_count = 0

        def streaming_factory(**_kw):
            async def first_call_raises():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise HTTPException(
                        status_code=500,
                        detail="An internal error occurred while executing the flow.",
                    )
                yield "end", {"result": response_text}

            return first_call_raises()

        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=_make_intent("generate_component"),
            ),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=streaming_factory),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_success),
            patch(f"{MODULE}.validate_component_runtime", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=2,
            )
            events = await _collect_events(gen)

            # Must retry — at least 2 calls to the streaming flow executor
            assert call_count >= 2, (
                f"Expected retry after flow execution error, but execute_flow_file_streaming "
                f"was called only {call_count} time(s)."
            )

            # Final event should be a complete event with validated=True
            complete_events = [e for e in events if '"event": "complete"' in e]
            assert complete_events, "Expected a complete event after successful retry"
            assert any('"validated": true' in e.lower() for e in complete_events), (
                f"Expected validated=true in complete event after successful retry. Events: {complete_events}"
            )

    @pytest.mark.asyncio
    async def test_should_emit_error_when_no_result(self):
        """Should emit error event when flow returns no result."""
        flow_gen = _make_flow_events([])  # No events = no result

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
            )
            events = await _collect_events(gen)

            error_events = [e for e in events if "error" in e.lower() or "no result" in e.lower()]
            assert len(error_events) >= 1


class TestFlowProposalReady:
    """Tests for the flow_proposal_ready signal.

    Emitted only when a build-from-scratch set_flow action was produced by the
    agent during a build_flow intent. The signal lets the frontend gate the
    destructive canvas replacement behind an explicit user Continue/Dismiss
    step. Incremental edits (add_component, connect, configure, edit_field)
    MUST NOT trigger this signal — they keep applying live to the canvas.
    """

    @pytest.mark.asyncio
    async def test_should_emit_flow_proposal_ready_when_build_flow_intent_with_set_flow_event(self):
        """When agent emits a set_flow action during build_flow intent, emit flow_proposal_ready."""
        flow_gen = _make_flow_events([("end", {"result": "Flow built"})])
        # First drain returns set_flow (build_flow tool fired); subsequent drains return [].
        drain_calls = [[{"action": "set_flow", "flow": {"data": {"nodes": [], "edges": []}}}], []]

        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=_make_intent("build_flow"),
            ),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
            patch(f"{MODULE}.drain_flow_events", side_effect=drain_calls + [[]] * 10),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="build me a chatbot",
                global_variables={},
            )
            events = await _collect_events(gen)

            proposal_events = [e for e in events if "flow_proposal_ready" in e]
            assert proposal_events, f"Expected flow_proposal_ready step in SSE stream. Events: {events}"

    @pytest.mark.asyncio
    async def test_should_not_emit_flow_proposal_ready_when_build_flow_intent_with_only_incremental_edits(self):
        """Incremental edits (add_component / configure) must not trigger the proposal gate."""
        flow_gen = _make_flow_events([("end", {"result": "Edits applied"})])
        drain_calls = [
            [
                {"action": "add_component", "node": {"id": "n1"}},
                {"action": "configure", "component_id": "n1", "params": {"x": 1}},
            ],
            [],
        ]

        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=_make_intent("build_flow"),
            ),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
            patch(f"{MODULE}.drain_flow_events", side_effect=drain_calls + [[]] * 10),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="add a chatinput",
                global_variables={},
            )
            events = await _collect_events(gen)

            assert not any("flow_proposal_ready" in e for e in events), (
                f"Did NOT expect flow_proposal_ready for incremental-edits-only run. Events: {events}"
            )

    @pytest.mark.asyncio
    async def test_should_not_emit_flow_proposal_ready_for_generate_component_intent(self):
        """Component generation path never emits the flow proposal signal."""
        flow_gen = _make_flow_events([("end", {"result": "class Foo(Component): pass"})])

        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=_make_intent("generate_component"),
            ),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
            patch(f"{MODULE}.drain_flow_events", return_value=[]),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
            )
            events = await _collect_events(gen)

            assert not any("flow_proposal_ready" in e for e in events)

    @pytest.mark.asyncio
    async def test_should_not_emit_flow_proposal_ready_for_question_intent(self):
        """Q&A path never emits the flow proposal signal."""
        flow_gen = _make_flow_events([("token", "Langflow is..."), ("end", {"result": "Langflow is..."})])

        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=_make_intent("question"),
            ),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
            patch(f"{MODULE}.drain_flow_events", return_value=[]),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="what is langflow",
                global_variables={},
            )
            events = await _collect_events(gen)

            assert not any("flow_proposal_ready" in e for e in events)

    @pytest.mark.asyncio
    async def test_should_emit_flow_proposal_ready_before_complete_event(self):
        """The flow_proposal_ready step must precede the complete event.

        The frontend uses this ordering to render the Continue gate before
        finalizing the message — if `complete` arrived first the message
        would transition to its terminal state and the gate would never render.
        """
        flow_gen = _make_flow_events([("end", {"result": "ok"})])
        drain_calls = [[{"action": "set_flow", "flow": {"data": {"nodes": [], "edges": []}}}], []]

        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=_make_intent("build_flow"),
            ),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
            patch(f"{MODULE}.drain_flow_events", side_effect=drain_calls + [[]] * 10),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="build",
                global_variables={},
            )
            events = await _collect_events(gen)

            proposal_idx = next(
                (i for i, e in enumerate(events) if "flow_proposal_ready" in e),
                -1,
            )
            complete_idx = next(
                (i for i, e in enumerate(events) if '"event": "complete"' in e),
                -1,
            )
            assert proposal_idx >= 0, "flow_proposal_ready missing"
            assert complete_idx >= 0, "complete event missing"
            assert proposal_idx < complete_idx, (
                f"flow_proposal_ready (idx {proposal_idx}) must come before complete (idx {complete_idx})"
            )


class TestCurrentUserIdContextVarIsolation:
    """SECURITY regression — ``_current_user_id_var`` MUST stay clean across requests.

    Bug shape: ``set_current_user_id`` was called above the ``try:`` block,
    leaving a 37-line gap in which an exception (e.g. inside
    ``inject_conversation_history`` or any pre-try helper) would bypass
    the matching ``reset_current_user_id`` in the ``finally`` clause. The
    next request reusing the same asyncio task would inherit the stale
    user_id and resolve the wrong user's components / registry overlay.
    """

    @pytest.mark.asyncio
    async def test_should_not_leak_current_user_id_when_pre_try_setup_raises(self):
        from langflow.agentic.services.user_components_context import (
            current_user_id,
            reset_current_user_id,
        )

        # Start from a known-clean state so the post-raise assertion is
        # unambiguous (this is also how a freshly spawned asyncio task arrives).
        reset_current_user_id()
        assert current_user_id() is None

        def boom(*_args, **_kwargs):
            msg = "simulated mid-handler exception in the pre-try setup gap"
            raise RuntimeError(msg)

        with (
            patch(f"{MODULE}.classify_intent", AsyncMock(return_value=_make_intent())),
            # inject_conversation_history runs in the gap between set_current_user_id
            # and the main try block — forcing it to raise reproduces the leak.
            patch(f"{MODULE}.inject_conversation_history", boom),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
                session_id="session-leak-test",
                user_id="user-alice",
            )
            with pytest.raises(RuntimeError, match="simulated mid-handler exception"):
                await _collect_events(gen)

        assert current_user_id() is None, (
            "ContextVar leaked: next request on this asyncio task would inherit "
            "'user-alice' as the current_user_id. set_current_user_id must live "
            "inside the same try/finally that resets it."
        )
