"""verify_flow — the Tier-1+Tier-2 validation loop (deps injected).

Orchestrates: ensure-agent-model (deterministic, never looped on) →
Tier-1 static → Tier-2 graph build. A fixable deterministic error is fed
back to the agent and re-validated, bounded by a hard attempt cap. A
flow that is valid + builds but whose Agent has no usable model is
delivered with an honest caveat (NEEDS_CAVEAT), never looped. Never
silently delivers a broken flow; never leaks secrets in the caveat.
"""

from __future__ import annotations

import pytest
from langflow.agentic.services.flow_agent_model import AgentModelOutcome
from langflow.agentic.services.flow_graph_build_check import BuildCheckResult
from langflow.agentic.services.flow_static_validation import FlowValidationReport
from langflow.agentic.services.flow_validation import (
    FlowVerifyStatus,
    verify_flow,
)


def _flow():
    return {"id": "f", "name": "f", "data": {"nodes": [], "edges": []}}


def _ok_report():
    return FlowValidationReport(ok=True)


def _bad_report(msg):
    return FlowValidationReport(ok=False, errors=[msg])


async def _build_ok(**_kw):
    return BuildCheckResult(ok=True)


async def _verify(**kw):
    base = {
        "flow": _flow(),
        "flow_id": "flow-1",
        "user_id": "u1",
        "agent_model_fn": lambda _f: AgentModelOutcome.NONE_NEEDED,
        "static_fn": lambda _f: _ok_report(),
        "build_fn": _build_ok,
        "fix_fn": None,
    }
    base.update(kw)
    if base["fix_fn"] is None:

        async def _no_fix(_err):
            return None

        base["fix_fn"] = _no_fix
    return await verify_flow(**base)


class TestVerifyFlow:
    @pytest.mark.asyncio
    async def test_should_pass_when_static_and_build_ok_and_no_agent_needs_a_model(self):
        result = await _verify()
        assert result.status is FlowVerifyStatus.PASSED
        assert result.attempts == 1
        assert result.caveat is None

    @pytest.mark.asyncio
    async def test_should_pass_silently_when_agent_model_was_auto_assigned(self):
        result = await _verify(agent_model_fn=lambda _f: AgentModelOutcome.ASSIGNED)
        assert result.status is FlowVerifyStatus.PASSED
        assert result.caveat is None  # auto-assign is invisible, no caveat

    @pytest.mark.asyncio
    async def test_should_caveat_without_looping_when_no_provider_for_agent(self):
        fix_calls = []

        async def fix(err):
            fix_calls.append(err)
            return _flow()

        result = await _verify(
            agent_model_fn=lambda _f: AgentModelOutcome.NO_PROVIDER,
            fix_fn=fix,
        )
        assert result.status is FlowVerifyStatus.NEEDS_CAVEAT
        assert fix_calls == []  # NEVER loop on the no-model case
        assert result.caveat is not None
        assert "model" in result.caveat.lower()

    @pytest.mark.asyncio
    async def test_should_retry_then_pass_when_a_tier1_error_is_fixed(self):
        reports = [_bad_report("Edge type mismatch on Agent-1"), _ok_report()]

        async def fix(_err):
            return _flow()

        result = await _verify(static_fn=lambda _f: reports.pop(0), fix_fn=fix)
        assert result.status is FlowVerifyStatus.PASSED
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_should_retry_then_pass_when_a_tier2_build_error_is_fixed(self):
        builds = [BuildCheckResult(ok=False, error="Attribute build_output not found"), BuildCheckResult(ok=True)]

        async def build_fn(**_kw):
            return builds.pop(0)

        async def fix(_err):
            return _flow()

        result = await _verify(build_fn=build_fn, fix_fn=fix)
        assert result.status is FlowVerifyStatus.PASSED
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_should_fail_after_exhausting_attempts_on_a_persistent_error(self):
        calls = {"n": 0}

        async def fix(_err):
            calls["n"] += 1
            return _flow()

        result = await _verify(
            static_fn=lambda _f: _bad_report("still broken"),
            fix_fn=fix,
            max_attempts=3,
        )
        assert result.status is FlowVerifyStatus.FAILED
        assert result.attempts == 3
        assert calls["n"] == 2  # fix between attempts: 3 attempts → 2 fixes (cost ceiling)
        assert result.caveat is not None
        assert "3" in result.caveat

    @pytest.mark.asyncio
    async def test_should_fail_immediately_when_the_agent_cannot_fix(self):
        result = await _verify(static_fn=lambda _f: _bad_report("broken"))
        assert result.status is FlowVerifyStatus.FAILED
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_should_not_leak_a_secret_in_the_caveat(self):
        async def build_fn(**_kw):
            return BuildCheckResult(ok=False, error="auth failed api key sk-LEAKME1234567890SECRET")

        result = await _verify(build_fn=build_fn)
        assert "sk-LEAKME1234567890SECRET" not in (result.caveat or "")

    @pytest.mark.asyncio
    async def test_should_respect_a_custom_max_attempts_of_one(self):
        calls = {"n": 0}

        async def fix(_err):
            calls["n"] += 1
            return _flow()

        result = await _verify(
            static_fn=lambda _f: _bad_report("broken"),
            fix_fn=fix,
            max_attempts=1,
        )
        assert result.status is FlowVerifyStatus.FAILED
        assert result.attempts == 1
        assert calls["n"] == 0  # no fix turn when cap is 1
