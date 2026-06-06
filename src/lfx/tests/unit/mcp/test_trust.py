"""Unit tests for the MCP pre-execution trust verification hook.

Acceptance criteria (from issue #13333 and reviewer comment):
1. When no verifier is configured, tool calls proceed with zero overhead.
2. A verifier that returns ALLOW lets the call through.
3. A verifier that returns DENY raises PermissionError before the tool runs.
4. A verifier that returns REQUIRE_APPROVAL raises PermissionError before the tool runs.
5. A verifier that returns WARN emits a warning but still dispatches the call.
6. The verifier always receives a fresh MCPToolCall — decisions are never
   reused across different (server_uri, tool_name, parameters_digest) tuples.
7. MCPToolCall.parameters_digest differs when parameters differ.
8. MCPToolCall.server_origin is derived from server_uri automatically.
"""

from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock

import pytest
from lfx.base.mcp.trust import MCPToolCall, TrustDecision, TrustState, TrustVerifier, run_trust_check

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AllowVerifier:
    async def verify(self, call: MCPToolCall) -> TrustDecision:
        return TrustDecision(state=TrustState.ALLOW)


class _DenyVerifier:
    def __init__(self, reason: str = "untrusted_origin") -> None:
        self._reason = reason

    async def verify(self, call: MCPToolCall) -> TrustDecision:
        return TrustDecision(state=TrustState.DENY, reason_code=self._reason)


class _ApprovalVerifier:
    async def verify(self, call: MCPToolCall) -> TrustDecision:
        return TrustDecision(state=TrustState.REQUIRE_APPROVAL, reason_code="needs_approval")


class _WarnVerifier:
    async def verify(self, call: MCPToolCall) -> TrustDecision:
        return TrustDecision(state=TrustState.WARN, reason_code="low_trust_score")


class _RecordingVerifier:
    """Captures every MCPToolCall it receives."""

    def __init__(self) -> None:
        self.calls: list[MCPToolCall] = []

    async def verify(self, call: MCPToolCall) -> TrustDecision:
        self.calls.append(call)
        return TrustDecision(state=TrustState.ALLOW)


# ---------------------------------------------------------------------------
# MCPToolCall unit tests
# ---------------------------------------------------------------------------


class TestMCPToolCall:
    def test_parameters_digest_is_sha256_of_canonical_json(self):
        call = MCPToolCall(server_uri="https://srv/mcp", tool_name="search", parameters={"q": "hello"})
        expected = hashlib.sha256(json.dumps({"q": "hello"}, sort_keys=True).encode()).hexdigest()
        assert call.parameters_digest == expected

    def test_parameters_digest_differs_for_different_params(self):
        a = MCPToolCall(server_uri="https://srv/mcp", tool_name="t", parameters={"x": 1})
        b = MCPToolCall(server_uri="https://srv/mcp", tool_name="t", parameters={"x": 2})
        assert a.parameters_digest != b.parameters_digest

    def test_parameters_digest_stable_across_key_order(self):
        a = MCPToolCall(server_uri="u", tool_name="t", parameters={"b": 2, "a": 1})
        b = MCPToolCall(server_uri="u", tool_name="t", parameters={"a": 1, "b": 2})
        assert a.parameters_digest == b.parameters_digest

    def test_server_origin_derived_from_uri(self):
        call = MCPToolCall(server_uri="https://api.example.com:8443/mcp", tool_name="t", parameters={})
        assert call.server_origin == "https://api.example.com:8443"

    def test_server_origin_http(self):
        call = MCPToolCall(server_uri="http://localhost:3000/mcp", tool_name="t", parameters={})
        assert call.server_origin == "http://localhost:3000"

    def test_server_origin_empty_for_stdio(self):
        call = MCPToolCall(server_uri="", tool_name="t", parameters={})
        assert call.server_origin == ""

    def test_explicit_server_origin_not_overwritten(self):
        call = MCPToolCall(
            server_uri="https://a.example.com/mcp",
            tool_name="t",
            parameters={},
            server_origin="custom-origin",
        )
        assert call.server_origin == "custom-origin"


# ---------------------------------------------------------------------------
# TrustDecision helpers
# ---------------------------------------------------------------------------


class TestTrustDecision:
    def test_decision_id_auto_generated(self):
        d1 = TrustDecision(state=TrustState.ALLOW)
        d2 = TrustDecision(state=TrustState.ALLOW)
        assert d1.decision_id != d2.decision_id

    def test_explicit_decision_id_preserved(self):
        d = TrustDecision(state=TrustState.DENY, decision_id="fixed-id")
        assert d.decision_id == "fixed-id"

    def test_default_metadata_is_empty_dict(self):
        d = TrustDecision(state=TrustState.ALLOW)
        assert d.metadata == {}

    def test_ttl_defaults_to_none(self):
        d = TrustDecision(state=TrustState.ALLOW)
        assert d.ttl is None


# ---------------------------------------------------------------------------
# TrustVerifier Protocol check
# ---------------------------------------------------------------------------


class TestTrustVerifierProtocol:
    def test_allow_verifier_satisfies_protocol(self):
        assert isinstance(_AllowVerifier(), TrustVerifier)

    def test_deny_verifier_satisfies_protocol(self):
        assert isinstance(_DenyVerifier(), TrustVerifier)


# ---------------------------------------------------------------------------
# run_trust_check – the core hook logic
# ---------------------------------------------------------------------------


class TestRunTrustCheckAllow:
    @pytest.mark.asyncio
    async def test_allow_does_not_raise(self):
        await run_trust_check(_AllowVerifier(), "search", "https://srv/mcp", {"q": "hi"})

    @pytest.mark.asyncio
    async def test_allow_does_not_call_warn_logger(self):
        warn = AsyncMock()
        await run_trust_check(_AllowVerifier(), "search", "https://srv/mcp", {}, warn_logger=warn)
        warn.assert_not_awaited()


class TestRunTrustCheckDeny:
    @pytest.mark.asyncio
    async def test_deny_raises_permission_error(self):
        with pytest.raises(PermissionError, match="untrusted_origin"):
            await run_trust_check(_DenyVerifier("untrusted_origin"), "t", "https://bad/mcp", {})

    @pytest.mark.asyncio
    async def test_deny_without_reason_still_raises(self):
        class _NoReason:
            async def verify(self, call: MCPToolCall) -> TrustDecision:
                return TrustDecision(state=TrustState.DENY)

        with pytest.raises(PermissionError):
            await run_trust_check(_NoReason(), "t", "", {})

    @pytest.mark.asyncio
    async def test_deny_message_contains_tool_name(self):
        with pytest.raises(PermissionError, match="my_tool"):
            await run_trust_check(_DenyVerifier(), "my_tool", "", {})


class TestRunTrustCheckRequireApproval:
    @pytest.mark.asyncio
    async def test_require_approval_raises_permission_error(self):
        with pytest.raises(PermissionError, match="needs_approval"):
            await run_trust_check(_ApprovalVerifier(), "t", "", {})

    @pytest.mark.asyncio
    async def test_require_approval_message_contains_tool_name(self):
        with pytest.raises(PermissionError, match="approve_me"):
            await run_trust_check(_ApprovalVerifier(), "approve_me", "", {})


class TestRunTrustCheckWarn:
    @pytest.mark.asyncio
    async def test_warn_does_not_raise(self):
        # warn must not raise — it allows the call through
        await run_trust_check(_WarnVerifier(), "t", "", {})

    @pytest.mark.asyncio
    async def test_warn_calls_warn_logger(self):
        warn = AsyncMock()
        await run_trust_check(_WarnVerifier(), "t", "", {}, warn_logger=warn)
        warn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_warn_log_contains_reason_code(self):
        warn = AsyncMock()
        await run_trust_check(_WarnVerifier(), "t", "", {}, warn_logger=warn)
        call_args = warn.call_args[0]
        assert any("low_trust_score" in str(a) for a in call_args)

    @pytest.mark.asyncio
    async def test_warn_log_contains_decision_id(self):
        class _WarnWithKnownId:
            async def verify(self, call: MCPToolCall) -> TrustDecision:
                return TrustDecision(state=TrustState.WARN, decision_id="test-id-999")

        warn = AsyncMock()
        await run_trust_check(_WarnWithKnownId(), "t", "", {}, warn_logger=warn)
        call_args = warn.call_args[0]
        assert any("test-id-999" in str(a) for a in call_args)

    @pytest.mark.asyncio
    async def test_warn_is_not_silently_allow(self):
        """Warn must never be treated as a silent allow — logger must be called."""
        warn = AsyncMock()
        await run_trust_check(_WarnVerifier(), "t", "", {}, warn_logger=warn)
        # If this assertion fails, warn became a silent allow.
        assert warn.await_count == 1, "warn state must always emit a log entry"


# ---------------------------------------------------------------------------
# Verifier receives correct context on every invocation (acceptance test #1)
# ---------------------------------------------------------------------------


class TestVerifierReceivesCorrectContext:
    @pytest.mark.asyncio
    async def test_verify_called_once_per_invocation(self):
        recorder = _RecordingVerifier()
        await run_trust_check(recorder, "search", "https://srv/mcp", {"q": "first"})
        await run_trust_check(recorder, "search", "https://srv/mcp", {"q": "second"})
        assert len(recorder.calls) == 2

    @pytest.mark.asyncio
    async def test_each_call_carries_correct_parameters(self):
        recorder = _RecordingVerifier()
        await run_trust_check(recorder, "t", "u", {"x": 1})
        await run_trust_check(recorder, "t", "u", {"x": 2})
        assert recorder.calls[0].parameters == {"x": 1}
        assert recorder.calls[1].parameters == {"x": 2}
        assert recorder.calls[0].parameters_digest != recorder.calls[1].parameters_digest

    @pytest.mark.asyncio
    async def test_server_uri_propagated(self):
        recorder = _RecordingVerifier()
        await run_trust_check(recorder, "t", "https://trusted.example.com/mcp", {})
        assert recorder.calls[0].server_uri == "https://trusted.example.com/mcp"
        assert recorder.calls[0].server_origin == "https://trusted.example.com"

    @pytest.mark.asyncio
    async def test_tool_name_propagated(self):
        recorder = _RecordingVerifier()
        await run_trust_check(recorder, "my_special_tool", "https://srv/mcp", {})
        assert recorder.calls[0].tool_name == "my_special_tool"

    @pytest.mark.asyncio
    async def test_different_params_yield_different_digests(self):
        """Verify that parameter changes prevent decision reuse at the verifier level."""
        recorder = _RecordingVerifier()
        await run_trust_check(recorder, "t", "u", {"file": "/etc/passwd"})
        await run_trust_check(recorder, "t", "u", {"file": "/tmp/safe.txt"})
        assert recorder.calls[0].parameters_digest != recorder.calls[1].parameters_digest
