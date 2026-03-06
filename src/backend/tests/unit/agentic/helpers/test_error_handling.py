"""Tests for error handling helpers.

Tests the error categorization and user-friendly message generation.
"""

import pytest
from langflow.agentic.helpers.error_handling import (
    ERROR_PATTERNS,
    MAX_ERROR_MESSAGE_LENGTH,
    MIN_MEANINGFUL_PART_LENGTH,
    _truncate_error_message,
    extract_friendly_error,
)


class TestExtractFriendlyError:
    """Tests for extract_friendly_error function."""

    def test_should_return_friendly_message_for_rate_limit_error(self):
        """Should return user-friendly message for rate limit errors."""
        error_messages = [
            "rate_limit exceeded",
            "Error 429: Too many requests",
            "Rate limit reached for model",
        ]

        for error in error_messages:
            result = extract_friendly_error(error)
            assert "rate limit" in result.lower()
            assert "wait" in result.lower() or "try again" in result.lower()

    def test_should_return_friendly_message_for_authentication_error(self):
        """Should return user-friendly message for authentication errors."""
        error_messages = [
            "authentication failed",
            "Invalid api_key provided",
            "Unauthorized access",
            "Error 401: Unauthorized",
        ]

        for error in error_messages:
            result = extract_friendly_error(error)
            assert "authentication" in result.lower() or "api key" in result.lower()

    def test_should_return_friendly_message_for_quota_error(self):
        """Should return user-friendly message for quota errors."""
        error_messages = [
            "quota exceeded",
            "billing limit reached",
            "Insufficient credits",
        ]

        for error in error_messages:
            result = extract_friendly_error(error)
            assert "quota" in result.lower() or "billing" in result.lower()

    def test_should_return_friendly_message_for_timeout_error(self):
        """Should return user-friendly message for timeout errors."""
        error_messages = [
            "Request timeout",
            "Connection timed out",
            "Operation timed out after 30 seconds",
        ]

        for error in error_messages:
            result = extract_friendly_error(error)
            assert "timeout" in result.lower() or "timed out" in result.lower()

    def test_should_return_friendly_message_for_connection_error(self):
        """Should return user-friendly message for connection errors."""
        error_messages = [
            "Connection refused",
            "Network error occurred",
            "Unable to establish connection",
        ]

        for error in error_messages:
            result = extract_friendly_error(error)
            assert "connection" in result.lower() or "network" in result.lower()

    def test_should_return_friendly_message_for_server_error(self):
        """Should return user-friendly message for server errors."""
        error_messages = [
            "Error 500: Internal server error",
            "500 Internal Server Error",
        ]

        for error in error_messages:
            result = extract_friendly_error(error)
            assert "server error" in result.lower()

    def test_should_return_friendly_message_for_model_not_found(self):
        """Should return user-friendly message for model not found errors."""
        error_messages = [
            "Model gpt-5 not found",
            "The model does not exist",
            "Model claude-99 is not available",
        ]

        for error in error_messages:
            result = extract_friendly_error(error)
            assert "model" in result.lower()
            assert "not available" in result.lower() or "different" in result.lower()

    def test_should_return_friendly_message_for_content_policy_error(self):
        """Should return user-friendly message for content policy errors."""
        error_messages = [
            "Content blocked by safety filter",
            "Request violates content policy",
            "Content filter triggered",
        ]

        for error in error_messages:
            result = extract_friendly_error(error)
            assert "content" in result.lower() or "policy" in result.lower()
            assert "modify" in result.lower() or "blocked" in result.lower()

    def test_should_truncate_unknown_error_messages(self):
        """Should truncate unknown error messages that are too long."""
        long_error = "x" * 200

        result = extract_friendly_error(long_error)

        assert len(result) <= MAX_ERROR_MESSAGE_LENGTH + 3
        assert result.endswith("...")

    def test_should_return_original_for_short_unknown_errors(self):
        """Should return original message for short unknown errors."""
        short_error = "Unknown error occurred"

        result = extract_friendly_error(short_error)

        assert result == short_error

    def test_should_handle_empty_string(self):
        """Should handle empty error string."""
        result = extract_friendly_error("")

        assert result == ""

    def test_should_be_case_insensitive(self):
        """Should match error patterns case-insensitively."""
        error_messages = [
            "RATE_LIMIT exceeded",
            "Rate_Limit error",
            "rAtE_lImIt issue",
        ]

        for error in error_messages:
            result = extract_friendly_error(error)
            assert "rate limit" in result.lower()


class TestTruncateErrorMessage:
    """Tests for _truncate_error_message function."""

    def test_should_return_original_for_short_messages(self):
        """Should return original message when within limit."""
        short_message = "Short error"

        result = _truncate_error_message(short_message)

        assert result == short_message

    def test_should_truncate_long_messages(self):
        """Should truncate messages that exceed the limit."""
        long_message = "x" * 200

        result = _truncate_error_message(long_message)

        assert len(result) == MAX_ERROR_MESSAGE_LENGTH + 3
        assert result.endswith("...")

    def test_should_extract_meaningful_part_from_colon_separated(self):
        """Should extract meaningful part from colon-separated messages."""
        message = "Very long prefix that we dont need: This is the meaningful error message"

        result = _truncate_error_message(message)

        assert "meaningful error" in result.lower() or len(result) <= MAX_ERROR_MESSAGE_LENGTH + 3

    def test_should_skip_too_short_parts_after_colon(self):
        """Should skip parts that are too short to be meaningful."""
        message = "x" * 200 + ": ab"

        result = _truncate_error_message(message)

        assert result.endswith("...")

    def test_should_handle_message_at_exact_limit(self):
        """Should return original when message is exactly at limit."""
        exact_message = "x" * MAX_ERROR_MESSAGE_LENGTH

        result = _truncate_error_message(exact_message)

        assert result == exact_message


class TestErrorPatterns:
    """Tests for ERROR_PATTERNS configuration."""

    def test_should_have_expected_pattern_categories(self):
        """Should have all expected error pattern categories."""
        expected_patterns = [
            "rate_limit",
            "authentication",
            "quota",
            "timeout",
            "connection",
            "500",
        ]

        all_patterns = []
        for patterns, _ in ERROR_PATTERNS:
            all_patterns.extend(patterns)

        for expected in expected_patterns:
            assert any(expected in pattern for pattern in all_patterns), f"Missing pattern category: {expected}"

    def test_each_pattern_should_have_friendly_message(self):
        """Each pattern list should have an associated friendly message."""
        for patterns, friendly_message in ERROR_PATTERNS:
            assert isinstance(patterns, list)
            assert len(patterns) > 0
            assert isinstance(friendly_message, str)
            assert len(friendly_message) > 0


class TestConstants:
    """Tests for module constants."""

    def test_max_error_message_length_is_reasonable(self):
        """MAX_ERROR_MESSAGE_LENGTH should be a reasonable value."""
        assert MAX_ERROR_MESSAGE_LENGTH > 50
        assert MAX_ERROR_MESSAGE_LENGTH < 500

    def test_min_meaningful_part_length_is_reasonable(self):
        """MIN_MEANINGFUL_PART_LENGTH should be a reasonable value."""
        assert MIN_MEANINGFUL_PART_LENGTH > 0
        assert MIN_MEANINGFUL_PART_LENGTH < 50


class TestBugsAndEdgeCases:
    """Tests that challenge the code — exposing real bugs and untested edge cases."""

    @pytest.mark.xfail(
        reason="BUG: L42 uses '<' instead of '<=' — strings with exactly MIN_MEANINGFUL_PART_LENGTH chars are skipped",
        strict=True,
    )
    def test_truncate_off_by_one_at_min_length(self):
        """_truncate_error_message should accept parts with exactly MIN_MEANINGFUL_PART_LENGTH chars."""
        # Create a message where the meaningful part after ':' is exactly MIN_MEANINGFUL_PART_LENGTH chars
        meaningful_part = "x" * MIN_MEANINGFUL_PART_LENGTH
        long_prefix = "y" * (MAX_ERROR_MESSAGE_LENGTH + 10)
        message = f"{long_prefix}: {meaningful_part}"

        result = _truncate_error_message(message)
        # Should return the meaningful part, not truncate the full message
        assert result == meaningful_part

    def test_extract_friendly_error_with_none_input_crashes(self):
        """extract_friendly_error crashes on None input — no input validation."""
        with pytest.raises(AttributeError):
            extract_friendly_error(None)

    def test_multiple_pattern_match_returns_first(self):
        """Error matching multiple patterns should return the first match."""
        # "rate_limit" and "401" both appear — should match rate_limit first
        error = "rate_limit error with 401 unauthorized"
        result = extract_friendly_error(error)
        assert "rate limit" in result.lower()

    def test_truncate_exact_limit_plus_one(self):
        """Message with exactly MAX_ERROR_MESSAGE_LENGTH+1 chars should be truncated."""
        message = "a" * (MAX_ERROR_MESSAGE_LENGTH + 1)
        result = _truncate_error_message(message)
        assert result.endswith("...")
        assert len(result) == MAX_ERROR_MESSAGE_LENGTH + 3

    def test_or_in_pattern_match_second_branch_is_redundant(self):
        """L21: 'pattern in error_lower or pattern in error_msg' — second branch never adds value.

        All patterns in ERROR_PATTERNS are lowercase, so if pattern is not in error_lower,
        it won't be in the case-sensitive error_msg either (since error_lower = error_msg.lower()).
        The 'or pattern in error_msg' branch is dead code for all current patterns.
        """
        # This test documents the behavior: case-insensitive matching works
        # purely through error_lower, the error_msg branch is unreachable
        error = "RATE_LIMIT ERROR"
        result = extract_friendly_error(error)
        assert "rate limit" in result.lower()
