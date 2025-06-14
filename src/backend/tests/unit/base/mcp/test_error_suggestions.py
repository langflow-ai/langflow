import pytest
from langflow.base.mcp.error_suggestions import (
    get_connection_error_suggestions,
    get_validation_error_suggestions,
)


class TestErrorSuggestions:
    """Basic sanity checks for the error suggestion helpers."""

    @pytest.mark.parametrize(
        ("error_msg", "expected_keyword"),
        [
            ("Connection timeout after 30s", "timeout"),
            ("Command not found: 'invalid'", "command"),
            ("connection refused", "connection"),
        ],
    )
    def test_connection_error_suggestions(self, error_msg: str, expected_keyword: str):
        suggestions = get_connection_error_suggestions(error_msg)
        # Ensure at least one suggestion returned and keyword present for rough match
        assert suggestions, "No suggestions returned for connection error"
        joined = " ".join(suggestions).lower()
        assert expected_keyword in joined

    @pytest.mark.parametrize(
        ("error_msg", "expected_keyword"),
        [
            ("Invalid URL format", "url"),
            ("Missing ENV config", "env"),
            ("command not found", "command"),
        ],
    )
    def test_validation_error_suggestions(self, error_msg: str, expected_keyword: str):
        suggestions = get_validation_error_suggestions(error_msg)
        assert suggestions, "No suggestions returned for validation error"
        joined = " ".join(suggestions).lower()
        assert expected_keyword in joined
