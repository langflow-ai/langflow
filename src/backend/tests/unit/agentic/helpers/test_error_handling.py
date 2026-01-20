"""Tests for error handling and message extraction."""

from langflow.agentic.helpers.error_handling import (
    ERROR_PATTERNS,
    MAX_ERROR_MESSAGE_LENGTH,
    _truncate_error_message,
    extract_friendly_error,
)


class TestExtractFriendlyError:
    """Tests for extract_friendly_error function."""

    def test_should_return_friendly_message_for_rate_limit_429(self):
        error = "Error 429: Rate limit exceeded"

        result = extract_friendly_error(error)

        assert result == "Rate limit exceeded. Please wait a moment and try again."

    def test_should_return_friendly_message_for_rate_limit_keyword(self):
        error = "You have hit the rate_limit for this API"

        result = extract_friendly_error(error)

        assert result == "Rate limit exceeded. Please wait a moment and try again."

    def test_should_return_friendly_message_for_authentication_error(self):
        error = "Authentication failed: invalid api_key"

        result = extract_friendly_error(error)

        assert result == "Authentication failed. Check your API key."

    def test_should_return_friendly_message_for_401_unauthorized(self):
        error = "HTTP 401: Unauthorized access"

        result = extract_friendly_error(error)

        assert result == "Authentication failed. Check your API key."

    def test_should_return_friendly_message_for_quota_exceeded(self):
        error = "Your quota has been exceeded"

        result = extract_friendly_error(error)

        assert result == "API quota exceeded. Please check your account billing."

    def test_should_return_friendly_message_for_billing_issue(self):
        error = "Billing account not active"

        result = extract_friendly_error(error)

        assert result == "API quota exceeded. Please check your account billing."

    def test_should_return_friendly_message_for_timeout(self):
        error = "Request timed out after 30 seconds"

        result = extract_friendly_error(error)

        assert result == "Request timed out. Please try again."

    def test_should_return_friendly_message_for_connection_error(self):
        error = "Connection refused to API endpoint"

        result = extract_friendly_error(error)

        assert result == "Connection error. Please check your network and try again."

    def test_should_return_friendly_message_for_network_error(self):
        error = "Network unreachable"

        result = extract_friendly_error(error)

        assert result == "Connection error. Please check your network and try again."

    def test_should_return_friendly_message_for_500_error(self):
        error = "HTTP 500: Internal server error"

        result = extract_friendly_error(error)

        assert result == "Server error. Please try again later."

    def test_should_return_friendly_message_for_model_not_found(self):
        error = "Model 'gpt-5' not found in available models"

        result = extract_friendly_error(error)

        assert result == "Model not available. Please select a different model."

    def test_should_return_friendly_message_for_model_does_not_exist(self):
        error = "The model specified does not exist"

        result = extract_friendly_error(error)

        assert result == "Model not available. Please select a different model."

    def test_should_return_friendly_message_for_content_filter(self):
        error = "Content filter blocked the request"

        result = extract_friendly_error(error)

        assert result == "Request blocked by content policy. Please modify your prompt."

    def test_should_return_friendly_message_for_content_policy(self):
        error = "Violated content policy guidelines"

        result = extract_friendly_error(error)

        assert result == "Request blocked by content policy. Please modify your prompt."

    def test_should_return_friendly_message_for_safety_filter(self):
        error = "Content safety filter triggered"

        result = extract_friendly_error(error)

        assert result == "Request blocked by content policy. Please modify your prompt."

    def test_should_truncate_unknown_long_error(self):
        long_error = "x" * 200

        result = extract_friendly_error(long_error)

        assert len(result) <= MAX_ERROR_MESSAGE_LENGTH + 3  # +3 for "..."
        assert result.endswith("...")

    def test_should_return_short_unknown_error_as_is(self):
        short_error = "Unknown error occurred"

        result = extract_friendly_error(short_error)

        assert result == short_error

    def test_should_handle_case_insensitive_matching(self):
        error = "RATE_LIMIT exceeded"

        result = extract_friendly_error(error)

        assert result == "Rate limit exceeded. Please wait a moment and try again."


class TestTruncateErrorMessage:
    """Tests for _truncate_error_message helper function."""

    def test_should_return_short_message_unchanged(self):
        short_msg = "Short error message"

        result = _truncate_error_message(short_msg)

        assert result == short_msg

    def test_should_truncate_long_message_with_ellipsis(self):
        long_msg = "x" * 200

        result = _truncate_error_message(long_msg)

        assert len(result) == MAX_ERROR_MESSAGE_LENGTH + 3
        assert result.endswith("...")

    def test_should_extract_meaningful_part_from_colon_separated(self):
        error = "Error: This is the meaningful part of the message"

        result = _truncate_error_message(error)

        assert "meaningful part" in result

    def test_should_use_first_valid_part_from_colon_separated(self):
        error = "E: Short: This is a longer meaningful message that should be used"

        result = _truncate_error_message(error)

        assert len(result) < MAX_ERROR_MESSAGE_LENGTH

    def test_should_handle_message_at_exact_limit(self):
        exact_msg = "x" * MAX_ERROR_MESSAGE_LENGTH

        result = _truncate_error_message(exact_msg)

        assert result == exact_msg
        assert not result.endswith("...")

    def test_should_handle_empty_message(self):
        result = _truncate_error_message("")

        assert result == ""


class TestErrorPatternsConstant:
    """Tests for ERROR_PATTERNS constant structure."""

    def test_should_have_patterns_as_list_of_tuples(self):
        assert isinstance(ERROR_PATTERNS, list)
        for item in ERROR_PATTERNS:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_should_have_list_of_strings_as_first_element(self):
        for patterns, _ in ERROR_PATTERNS:
            assert isinstance(patterns, list)
            for pattern in patterns:
                assert isinstance(pattern, str)

    def test_should_have_string_message_as_second_element(self):
        for _, message in ERROR_PATTERNS:
            assert isinstance(message, str)
            assert len(message) > 0


class TestEdgeCases:
    """Edge case tests for error handling."""

    def test_should_handle_none_like_behavior_gracefully(self):
        # Empty string should not raise
        result = extract_friendly_error("")
        assert result == ""

    def test_should_handle_special_characters(self):
        error = "Error with special chars: <>&'\""

        result = extract_friendly_error(error)

        assert result is not None

    def test_should_handle_unicode_characters(self):
        error = "Error with unicode: éàü 中文 😀"

        result = extract_friendly_error(error)

        assert result is not None

    def test_should_handle_newlines_in_error(self):
        error = "Error message\nwith\nnewlines"

        result = extract_friendly_error(error)

        assert result is not None

    def test_should_match_pattern_in_longer_error(self):
        error = "A very long error message that contains rate_limit somewhere in the middle of it"

        result = extract_friendly_error(error)

        assert result == "Rate limit exceeded. Please wait a moment and try again."
