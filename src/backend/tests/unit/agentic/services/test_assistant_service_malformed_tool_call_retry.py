"""Malformed tool-call 500s from Ollama must retry, not kill the build.

Reproduced live (2026-06-12, gpt-oss:20b): the model emitted a near-perfect
``build_flow`` spec but broke the args JSON; Ollama 500'd with "error parsing
tool call ... invalid character ']'". The failure is fast and transient
(resampling usually fixes it), yet builds treated it as terminal.
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

MALFORMED_TOOL_CALL_ERROR = (
    "Error building Component Agent: \n\nerror parsing tool call: "
    'raw=\'{"spec":"name: Random Flow Example..."}]}\', '
    "err=invalid character ']' after top-level value (status code: 500)."
)


def _collect_event_payloads(events: list[str]) -> list[dict]:
    parsed: list[dict] = []
    for ev in events:
        parsed.extend(json.loads(line[len("data: ") :]) for line in ev.splitlines() if line.startswith("data: "))
    return parsed


async def _collect(agen):
    return [e async for e in agen]


class _MalformedThenSuccessFactory:
    def __init__(self, fail_count: int) -> None:
        self.fail_count = fail_count
        self.calls = 0

    def __call__(self, **_kwargs):
        self.calls += 1
        calls = self.calls

        async def gen():
            if calls <= self.fail_count:
                raise FlowExecutionError(original_error_message=MALFORMED_TOOL_CALL_ERROR)
            yield "end", {"result": "Built it."}

        return gen()


class TestMalformedToolCallRetry:
    @pytest.mark.asyncio
    async def test_should_retry_build_when_tool_call_parsing_fails_transiently(self):
        factory = _MalformedThenSuccessFactory(fail_count=1)

        def drain():
            if factory.calls >= 2:
                return [{"action": "set_flow", "flow": {"data": {"nodes": [], "edges": []}}}]
            return []

        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=IntentResult(intent="build_flow", translation="t"),
            ),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=factory),
            patch(f"{MODULE}.drain_flow_events", side_effect=drain),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect(
                execute_flow_with_validation_streaming(
                    flow_filename="TestFlow",
                    input_value="crie um flow com 5 componentes aleatorios",
                    global_variables={},
                    model_name="gpt-oss:20b",
                    max_retries=2,
                )
            )

        payloads = _collect_event_payloads(events)
        event_types = [p.get("event") for p in payloads]
        assert factory.calls == 2, f"Expected a retry after the malformed tool call, executor ran {factory.calls}x"
        assert "error" not in event_types, f"Transient parse failure must not be terminal, got: {event_types}"
        assert "complete" in event_types

    @pytest.mark.asyncio
    async def test_should_surface_error_when_every_attempt_produces_malformed_tool_calls(self):
        factory = _MalformedThenSuccessFactory(fail_count=99)
        with (
            patch(
                f"{MODULE}.classify_intent",
                new_callable=AsyncMock,
                return_value=IntentResult(intent="build_flow", translation="t"),
            ),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=factory),
            patch(f"{MODULE}.drain_flow_events", return_value=[]),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect(
                execute_flow_with_validation_streaming(
                    flow_filename="TestFlow",
                    input_value="crie um flow",
                    global_variables={},
                    model_name="gpt-oss:20b",
                    max_retries=1,
                )
            )

        payloads = _collect_event_payloads(events)
        error_events = [p for p in payloads if p.get("event") == "error"]
        assert error_events, "Exhausted malformed-tool-call retries must end in an explicit error"
        assert "malformed tool call" in error_events[0]["message"].lower()
