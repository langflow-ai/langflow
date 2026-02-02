"""Tests for error handling helpers.

Tests the error categorization and user-friendly message generation.
"""

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

        assert len(result) <= MAX_ERROR_MESSAGE_LENGTH + 3  # +3 for "..."
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

        # Should prefer the meaningful part after colon
        assert "meaningful error" in result.lower() or len(result) <= MAX_ERROR_MESSAGE_LENGTH + 3

    def test_should_skip_too_short_parts_after_colon(self):
        """Should skip parts that are too short to be meaningful."""
        message = "x" * 200 + ": ab"  # "ab" is too short

        result = _truncate_error_message(message)

        # Should fall back to truncation since "ab" is too short
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
