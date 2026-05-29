r"""Bug 4 [P2] — generic build errors must preserve diagnostic context.

The pre-fix ``_truncate_error_message`` returns the FIRST colon-segment
between 10 and 150 chars. For a wrapped error like::

    Error building Component Agent: \nError code: 403 - {'error': {...}}

it returns ``"Error building Component Agent"`` and discards the actually
useful cause (the 403 / model_not_found / underlying provider message).
The user then sees a vague toast with zero hint about what went wrong.

Reference: PR-12575 OPEN BUG #4. The encoding-bug instance was fixed in
``ddcad681``, but the pattern still strips diagnostic context for every
``FlowExecutionError`` whose underlying message doesn't match a friendly
``ERROR_PATTERNS`` entry. Bugs 1 and 2 resolved the SPECIFIC provider
cases; this test guards the cross-cutting pattern so any future wrapped
error keeps the meaningful detail.
"""

from __future__ import annotations

from langflow.agentic.helpers.error_handling import (
    MAX_ERROR_MESSAGE_LENGTH,
    extract_friendly_error,
)


class TestPreservesUnderlyingCauseForWrappedErrors:
    """Bug 4 — wrapped errors must surface the deepest meaningful segment."""

    def test_should_surface_underlying_message_when_component_wraps_provider_error(self):
        """RED before fix: returns 'Error building Component Agent' — the wrapper, not the cause.

        Post-fix: must surface the cause (provider message, status code,
        or both) so the user can act on the actual failure.
        """
        wrapped = (
            "Error building Component Agent: \nError code: 403 - "
            "{'error': {'message': 'Project proj_xxx does not have access "
            "to model gpt-5.5-pro', 'type': 'invalid_request_error', "
            "'param': None, 'code': 'model_not_found'}}"
        )
        result = extract_friendly_error(wrapped)

        # Must NOT be the bare wrapper (the pre-fix behavior).
        assert result != "Error building Component Agent", f"Returned the wrapper instead of the cause: {result!r}"
        # Must carry at least one diagnostic marker so the user knows what
        # actually failed.
        diagnostic_markers = (
            "gpt-5.5-pro",
            "does not have access",
            "model_not_found",
            "403",
        )
        assert any(marker in result for marker in diagnostic_markers), (
            f"Expected at least one diagnostic marker in result, got: {result!r}"
        )

    def test_should_surface_underlying_message_for_generic_component_wrap(self):
        """Non-provider wrap: must still strip the wrapper prefix and surface the cause."""
        wrapped = "Error building Component MyTool: ValueError: invalid configuration in field 'x'"
        result = extract_friendly_error(wrapped)

        assert result != "Error building Component MyTool", f"Returned the wrapper instead of the cause: {result!r}"
        assert "invalid configuration" in result or "field 'x'" in result, (
            f"Expected underlying detail in result, got: {result!r}"
        )

    def test_should_cap_at_max_length_even_when_preserving_cause(self):
        """Long deep-segment messages must still be capped (not unbounded)."""
        wrapped = "Error building Component X: " + ("a very long cause message " * 30)
        result = extract_friendly_error(wrapped)
        # Allow a small overhead for the leading wrap prefix or ellipsis.
        assert len(result) <= MAX_ERROR_MESSAGE_LENGTH + 50, f"Result exceeds cap, len={len(result)}: {result!r}"


class TestPreservesExistingFriendlyMappings:
    """Characterization: don't regress the ERROR_PATTERNS path."""

    def test_should_still_map_rate_limit(self):
        """Rate-limit pattern still wins over diagnostic surfacing."""
        result = extract_friendly_error("rate_limit exceeded: please retry later")
        assert "rate limit" in result.lower()

    def test_should_still_map_authentication(self):
        result = extract_friendly_error("authentication failed: bad api_key")
        assert "authentication" in result.lower() or "api key" in result.lower()
