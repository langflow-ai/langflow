"""Streaming fallback when the resolved Ollama model is not installed.

Reproduced live (2026-06-12, release-1.11.0, Ollama-only setup):
``POST /agentic/assist/stream`` without an explicit model resolves the
static catalog default ``llama3.3``; Ollama answers ``model 'llama3.3'
not found (status code: 404)`` and the stream ends in a terminal
``error`` event on attempt 1 — no fallback to any installed model.

After the fix the streamer must recognize the Ollama 404 phrasing as a
model-unavailable signal and walk the LIVE installed-model candidates
(via ``get_provider_model_candidates(provider, user_id=...)``) instead
of the static catalog.

Mock boundaries: ``execute_flow_file_streaming`` (the LLM/flow engine)
and ``get_live_models_for_provider`` (external Ollama server) — neither
is reproducible in CI. Intent classification is patched like in
``test_assistant_service_model_fallback.py``.
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
PROVIDER_MODULE = "langflow.agentic.services.provider_service"

OLLAMA_MODEL_NOT_FOUND_ERROR = "Error building Component Language Model: model 'llama3.3' not found (status code: 404)."

INSTALLED_OLLAMA_MODELS = [
    {"name": "gpt-oss:20b", "tool_calling": True},
    {"name": "llama3.2:latest", "tool_calling": True},
]


def _collect_event_payloads(events: list[str]) -> list[dict]:
    parsed: list[dict] = []
    for ev in events:
        parsed.extend(json.loads(line[len("data: ") :]) for line in ev.splitlines() if line.startswith("data: "))
    return parsed


async def _collect(gen):
    return [event async for event in gen]


class _OllamaNotFoundFlowFactory:
    """Raises the exact Ollama 404 error until a non-catalog model is used."""

    def __init__(self, fail_count: int) -> None:
        self.fail_count = fail_count
        self.calls: list[str] = []

    def __call__(self, *_args, **kwargs):
        model_name = kwargs.get("model_name") or ""
        self.calls.append(model_name)

        async def gen():
            if len(self.calls) <= self.fail_count:
                raise FlowExecutionError(original_error_message=OLLAMA_MODEL_NOT_FOUND_ERROR)
            yield ("end", {"result": "ok"})

        return gen()


class TestOllamaModelFallback:
    @pytest.mark.asyncio
    async def test_should_fall_back_to_installed_model_when_ollama_default_is_not_installed(self):
        factory = _OllamaNotFoundFlowFactory(fail_count=1)
        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=IntentResult(intent="question", translation="test"),
            ),
            patch(
                f"{MODULE}.execute_flow_file_streaming",
                side_effect=factory,
            ),
            patch(
                f"{PROVIDER_MODULE}.get_live_models_for_provider",
                return_value=INSTALLED_OLLAMA_MODELS,
                create=True,
            ),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={"MODEL_NAME": "llama3.3", "PROVIDER": "Ollama"},
                user_id="00000000-0000-0000-0000-000000000001",
                provider="Ollama",
                model_name="llama3.3",
                api_key_var="OLLAMA_BASE_URL",
                max_retries=0,
            )
            events = await _collect(gen)

        payloads = _collect_event_payloads(events)
        event_types = [p.get("event") for p in payloads]
        assert factory.calls == ["llama3.3", "gpt-oss:20b"], (
            f"Expected fallback to the installed gpt-oss:20b after llama3.3 404, got: {factory.calls}"
        )
        assert "error" not in event_types, f"Expected silent fallback (no error event), got: {event_types}"
        assert "complete" in event_types, f"Expected complete event after fallback, got: {event_types}"
