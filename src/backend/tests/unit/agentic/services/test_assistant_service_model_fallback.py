"""Bug 1 [P1] — model fallback chain on `model_not_found` errors.

When the default model the assistant resolves cannot be reached (typical
OpenAI 403 ``model_not_found`` because the user's project lacks access to
the catalog's default model, e.g. ``gpt-5.5-pro``), the streaming path
must transparently fall back to the next available model on the same
provider instead of surfacing ``Error building Component Agent`` to the
user.

When **every** candidate model is exhausted, the final SSE ``error``
event must name the provider and list the models tried — never a generic
``Error building Component Agent``.

Reference: PR-12575 OPEN BUG #1 backend log
``Project ... does not have access to model 'gpt-5.5-pro' ... 'code': 'model_not_found'``
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.flow_types import FlowExecutionError, IntentResult

MODULE = "langflow.agentic.services.assistant_service"

# The exact error wrapping the assistant receives from the LLM call when
# OpenAI returns 403 model_not_found. Lifted verbatim from
# PR-12575-bug-1-backend-log.txt so the test exercises the EXACT error
# path from the bug report.
_MODEL_NOT_FOUND_ERROR = (
    "Error building Component Agent: \n"
    "Error code: 403 - {'error': {'message': \"Project `proj_xxx` does not have access "
    "to model `gpt-5.5-pro`\", 'type': 'invalid_request_error', 'param': None, "
    "'code': 'model_not_found'}}"
)


def _make_intent(intent: str = "question", translation: str = "test") -> IntentResult:
    return IntentResult(intent=intent, translation=translation)


def _collect_event_payloads(events: list[str]) -> list[dict]:
    """Parse SSE event lines into dict payloads. Empty lines are dropped."""
    parsed: list[dict] = []
    for ev in events:
        parsed.extend(json.loads(line[len("data: ") :]) for line in ev.splitlines() if line.startswith("data: "))
    return parsed


async def _collect(gen):
    return [event async for event in gen]


class _FallbackFlowFactory:
    """Builds the ``execute_flow_file_streaming`` side-effect chain.

    The factory raises ``FlowExecutionError(model_not_found)`` for the
    first ``fail_count`` calls and yields a normal ``end`` event on the
    next call. Records which ``model_name`` each call was invoked with so
    the test can assert the fallback order.
    """

    def __init__(self, fail_count: int) -> None:
        self.fail_count = fail_count
        self.calls: list[str] = []

    def __call__(self, *_args, **kwargs):
        model_name = kwargs.get("model_name") or ""
        self.calls.append(model_name)

        async def gen():
            if len(self.calls) <= self.fail_count:
                # Raise EXACTLY as flow_executor.py does at line 255.
                raise FlowExecutionError(original_error_message=_MODEL_NOT_FOUND_ERROR)
            yield ("end", {"result": "ok"})

        return gen()


class TestModelFallbackOnModelNotFound:
    """Bug 1: default model returns model_not_found → fall back to next available."""

    @pytest.mark.asyncio
    async def test_should_fall_back_to_next_model_when_default_returns_model_not_found(self):
        """First model fails with model_not_found → next candidate runs and succeeds.

        RED before fix: assistant emits ``event: error`` with the generic
        ``Error building Component Agent`` truncation on the FIRST failure
        (no fallback attempted), so no ``complete`` event is ever emitted.
        """
        factory = _FallbackFlowFactory(fail_count=1)
        # Patch the candidate-list provider to return a deterministic order
        # so the test isn't coupled to the live model catalog.
        # ``create=True`` lets the RED test surface the real missing
        # behavior (no fallback attempted) rather than an AttributeError
        # on the symbol we're about to introduce.
        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=_make_intent("question"),
            ),
            patch(
                f"{MODULE}.execute_flow_file_streaming",
                side_effect=factory,
            ),
            patch(
                f"{MODULE}.get_provider_model_candidates",
                return_value=["gpt-5.5-pro", "gpt-4o", "gpt-4o-mini"],
                create=True,
            ),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={"MODEL_NAME": "gpt-5.5-pro", "PROVIDER": "OpenAI"},
                provider="OpenAI",
                model_name="gpt-5.5-pro",
                api_key_var="OPENAI_API_KEY",
                max_retries=0,
            )
            events = await _collect(gen)

        payloads = _collect_event_payloads(events)
        event_types = [p.get("event") for p in payloads]
        # Two calls expected: the default that failed + the fallback that succeeded.
        assert factory.calls == ["gpt-5.5-pro", "gpt-4o"], (
            f"Expected fallback to gpt-4o after gpt-5.5-pro failed, got: {factory.calls}"
        )
        # No error event should reach the client when the fallback succeeds.
        assert "error" not in event_types, f"Expected silent fallback (no error event), got events: {event_types}"
        assert "complete" in event_types, f"Expected complete event after fallback, got events: {event_types}"

    @pytest.mark.asyncio
    async def test_should_emit_clear_error_naming_provider_when_all_models_exhausted(self):
        """All candidate models return model_not_found → error event names provider + models.

        RED before fix: only the first model is attempted; the error event
        reads ``Error building Component Agent`` regardless of how many
        models exist on the provider.
        """
        factory = _FallbackFlowFactory(fail_count=10)  # always fail
        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=_make_intent("question"),
            ),
            patch(
                f"{MODULE}.execute_flow_file_streaming",
                side_effect=factory,
            ),
            patch(
                f"{MODULE}.get_provider_model_candidates",
                return_value=["gpt-5.5-pro", "gpt-4o"],
                create=True,
            ),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={"MODEL_NAME": "gpt-5.5-pro", "PROVIDER": "OpenAI"},
                provider="OpenAI",
                model_name="gpt-5.5-pro",
                api_key_var="OPENAI_API_KEY",
                max_retries=0,
            )
            events = await _collect(gen)

        payloads = _collect_event_payloads(events)
        error_payloads = [p for p in payloads if p.get("event") == "error"]
        assert factory.calls == ["gpt-5.5-pro", "gpt-4o"], f"Expected every candidate to be tried, got: {factory.calls}"
        assert len(error_payloads) == 1, (
            f"Expected exactly one error event after exhausting candidates, got: {payloads}"
        )
        msg = error_payloads[0].get("message", "")
        # Error must name the provider AND each tried model so the user can
        # act on it (switch provider, request access, etc.).
        assert "OpenAI" in msg, f"Error must name the provider, got: {msg!r}"
        assert "gpt-5.5-pro" in msg, f"Error must list tried models, got: {msg!r}"
        assert "gpt-4o" in msg, f"Error must list tried models, got: {msg!r}"

    @pytest.mark.asyncio
    async def test_should_not_fall_back_for_non_model_unavailable_errors(self):
        """Generic errors (rate limit, auth, network) must NOT trigger model fallback.

        Fallback is reserved for `model_not_found`-class errors per the
        bug-1 spec; an auth failure on model A means the same key will fail
        on model B too, and a rate-limit is transient. Falling back in those
        cases would mask the real problem.
        """
        calls: list[str] = []

        def factory(*_args, **kwargs):
            calls.append(kwargs.get("model_name") or "")

            # The ``yield`` keyword below is what makes ``gen`` an async
            # generator (vs. a coroutine returning a value). The streamer
            # only iterates it, so the yielded value is never consumed —
            # the raise on the first iteration is what propagates the error.
            async def gen():
                raise FlowExecutionError(
                    original_error_message="Error code: 401 - {'error': {'code': 'invalid_api_key'}}"
                )
                yield

            return gen()

        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=_make_intent("question"),
            ),
            patch(
                f"{MODULE}.execute_flow_file_streaming",
                side_effect=factory,
            ),
            patch(
                f"{MODULE}.get_provider_model_candidates",
                return_value=["gpt-5.5-pro", "gpt-4o", "gpt-4o-mini"],
                create=True,
            ),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={"MODEL_NAME": "gpt-5.5-pro", "PROVIDER": "OpenAI"},
                provider="OpenAI",
                model_name="gpt-5.5-pro",
                api_key_var="OPENAI_API_KEY",
                max_retries=0,
            )
            await _collect(gen)

        # Only the original model should be attempted — no fallback on auth errors.
        assert calls == ["gpt-5.5-pro"], f"Expected no fallback on auth error, got calls: {calls}"
