"""verify_built_flow — the run→classify→fix→retry loop (deps injected).

The real graph run and the LLM fix are injected so the loop's decision
logic is unit-testable in isolation: pass on success, retry fixable
bugs up to the cap, STOP immediately (no token burn) on external /
timeout errors, fail honestly when attempts are exhausted, and never
leak secrets in the caveat.
"""

from __future__ import annotations

import pytest
from langflow.agentic.services.flow_probe_input import PROBE_INPUT_TEXT
from langflow.agentic.services.flow_verification import (
    FlowVerificationStatus,
    verify_built_flow,
)


def _flow_with_chat_input(value=""):
    return {
        "name": "f",
        "data": {
            "nodes": [
                {
                    "id": "ChatInput-1",
                    "data": {"type": "ChatInput", "node": {"template": {"input_value": {"value": value}}}},
                }
            ],
            "edges": [],
        },
    }


def _ok(_flow):
    return {"result": "it worked", "metrics": {"duration_seconds": 1.0}}


class TestVerifyBuiltFlow:
    @pytest.mark.asyncio
    async def test_should_return_passed_when_first_run_succeeds(self):
        fix_calls = []

        async def run_fn(_flow):
            return _ok(_flow)

        async def fix_fn(err):
            fix_calls.append(err)

        result = await verify_built_flow(flow=_flow_with_chat_input(), run_fn=run_fn, fix_fn=fix_fn)

        assert result.status is FlowVerificationStatus.PASSED
        assert result.attempts == 1
        assert fix_calls == []  # never asked the agent to fix a working flow

    @pytest.mark.asyncio
    async def test_should_retry_then_pass_when_a_fixable_error_is_fixed(self):
        runs = []

        async def run_fn(flow):
            runs.append(flow)
            if len(runs) == 1:
                return {"error": "AttributeError: 'NoneType' object has no attribute 'text'"}
            return _ok(flow)

        async def fix_fn(_err):
            return _flow_with_chat_input("fixed")

        result = await verify_built_flow(flow=_flow_with_chat_input(), run_fn=run_fn, fix_fn=fix_fn)

        assert result.status is FlowVerificationStatus.PASSED
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_should_stop_and_caveat_on_external_resource_error_without_retrying(self):
        fix_calls = []

        async def run_fn(_flow):
            return {"error": "Incorrect API key provided"}

        async def fix_fn(err):
            fix_calls.append(err)
            return _flow_with_chat_input()

        result = await verify_built_flow(flow=_flow_with_chat_input(), run_fn=run_fn, fix_fn=fix_fn)

        assert result.status is FlowVerificationStatus.NEEDS_CAVEAT
        assert result.attempts == 1
        assert fix_calls == []  # did NOT burn an LLM attempt on an unfixable error
        assert result.caveat is not None
        assert "couldn't" in result.caveat.lower()

    @pytest.mark.asyncio
    async def test_should_stop_and_caveat_on_timeout_without_retrying(self):
        async def run_fn(_flow):
            return {"error": "The flow run timed out after 120s."}

        async def fix_fn(_err):
            msg = "fix_fn must not be called on timeout"
            raise AssertionError(msg)

        result = await verify_built_flow(flow=_flow_with_chat_input(), run_fn=run_fn, fix_fn=fix_fn)

        assert result.status is FlowVerificationStatus.NEEDS_CAVEAT
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_should_fail_after_exhausting_attempts_on_a_persistent_fixable_error(self):
        runs = []

        async def run_fn(flow):
            runs.append(flow)
            return {"error": "ValidationError: still broken"}

        async def fix_fn(_err):
            return _flow_with_chat_input("attempted fix")

        result = await verify_built_flow(flow=_flow_with_chat_input(), run_fn=run_fn, fix_fn=fix_fn, max_attempts=3)

        assert result.status is FlowVerificationStatus.FAILED
        assert result.attempts == 3
        assert len(runs) == 3  # hard cost ceiling enforced
        assert result.caveat is not None
        assert "3" in result.caveat

    @pytest.mark.asyncio
    async def test_should_stop_when_the_agent_cannot_produce_a_fix(self):
        runs = []

        async def run_fn(flow):
            runs.append(flow)
            return {"error": "KeyError: 'message'"}

        async def fix_fn(_err):
            return None  # agent gave up

        result = await verify_built_flow(flow=_flow_with_chat_input(), run_fn=run_fn, fix_fn=fix_fn)

        assert result.status is FlowVerificationStatus.FAILED
        assert len(runs) == 1  # no infinite loop when no fix is produced

    @pytest.mark.asyncio
    async def test_should_not_leak_a_secret_in_the_caveat(self):
        async def run_fn(_flow):
            return {"error": "Auth failed using api key sk-ABCD1234SECRETTOKEN5678"}

        async def fix_fn(_err): ...

        result = await verify_built_flow(flow=_flow_with_chat_input(), run_fn=run_fn, fix_fn=fix_fn)

        assert "sk-ABCD1234SECRETTOKEN5678" not in (result.caveat or "")

    @pytest.mark.asyncio
    async def test_should_apply_probe_input_before_running(self):
        seen = {}

        async def run_fn(flow):
            seen["value"] = flow["data"]["nodes"][0]["data"]["node"]["template"]["input_value"]["value"]
            return _ok(flow)

        async def fix_fn(_err): ...

        await verify_built_flow(flow=_flow_with_chat_input(""), run_fn=run_fn, fix_fn=fix_fn)

        assert seen["value"] == PROBE_INPUT_TEXT

    @pytest.mark.asyncio
    async def test_should_respect_a_custom_max_attempts_of_one(self):
        runs = []

        async def run_fn(flow):
            runs.append(flow)
            return {"error": "TypeError: broken"}

        async def fix_fn(_err):
            return _flow_with_chat_input()

        result = await verify_built_flow(flow=_flow_with_chat_input(), run_fn=run_fn, fix_fn=fix_fn, max_attempts=1)

        assert result.status is FlowVerificationStatus.FAILED
        assert len(runs) == 1
