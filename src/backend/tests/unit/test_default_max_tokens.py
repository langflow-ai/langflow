"""Tests for DEFAULT_MAX_TOKENS in unified_models.

Tests that DEFAULT_MAX_TOKENS is applied correctly when max_tokens
is None, 0, empty string, or invalid in the get_llm function.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest
from lfx.base.models.unified_models import DEFAULT_MAX_TOKENS, get_llm


def _make_model_config(provider="OpenAI", name="gpt-4"):
    """Create a minimal model config list for get_llm."""
    return [
        {
            "name": name,
            "provider": provider,
            "metadata": {
                "model_class": "ChatOpenAI",
                "api_key_param": "api_key",
                "model_name_param": "model",
                "max_tokens_field_name": "max_tokens",
            },
        }
    ]


class MockLLM:
    """Mock LLM class that stores kwargs."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs


MODULE = "lfx.base.models.unified_models"


class TestDefaultMaxTokensConstant:
    """Tests for the DEFAULT_MAX_TOKENS constant value."""

    def test_should_be_16384(self):
        """DEFAULT_MAX_TOKENS should be 16384."""
        assert DEFAULT_MAX_TOKENS == 16384

    def test_should_be_integer(self):
        """DEFAULT_MAX_TOKENS should be an integer."""
        assert isinstance(DEFAULT_MAX_TOKENS, int)

    def test_should_be_positive(self):
        """DEFAULT_MAX_TOKENS should be positive."""
        assert DEFAULT_MAX_TOKENS > 0


class TestGetLlmMaxTokens:
    """Tests that get_llm applies DEFAULT_MAX_TOKENS correctly."""

    @pytest.fixture
    def _mock_dependencies(self):
        """Mock external dependencies for get_llm."""
        with (
            patch(f"{MODULE}.get_api_key_for_provider", return_value="test-key"),
            patch(f"{MODULE}.get_model_class", return_value=MockLLM),
        ):
            yield

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_should_use_default_when_max_tokens_is_none(self):
        """get_llm with max_tokens=None should use DEFAULT_MAX_TOKENS."""
        result = get_llm(
            _make_model_config(),
            user_id=str(uuid4()),
            max_tokens=None,
        )

        assert result.kwargs["max_tokens"] == DEFAULT_MAX_TOKENS

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_should_use_default_when_max_tokens_is_zero(self):
        """get_llm with max_tokens=0 should use DEFAULT_MAX_TOKENS."""
        result = get_llm(
            _make_model_config(),
            user_id=str(uuid4()),
            max_tokens=0,
        )

        assert result.kwargs["max_tokens"] == DEFAULT_MAX_TOKENS

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_should_use_default_when_max_tokens_is_empty_string(self):
        """get_llm with max_tokens='' should use DEFAULT_MAX_TOKENS."""
        result = get_llm(
            _make_model_config(),
            user_id=str(uuid4()),
            max_tokens="",
        )

        assert result.kwargs["max_tokens"] == DEFAULT_MAX_TOKENS

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_should_use_provided_value_when_valid(self):
        """get_llm with max_tokens=1000 should use 1000."""
        result = get_llm(
            _make_model_config(),
            user_id=str(uuid4()),
            max_tokens=1000,
        )

        assert result.kwargs["max_tokens"] == 1000

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_should_use_default_when_max_tokens_is_invalid_string(self):
        """get_llm with max_tokens='invalid' should use DEFAULT_MAX_TOKENS."""
        result = get_llm(
            _make_model_config(),
            user_id=str(uuid4()),
            max_tokens="invalid",
        )

        assert result.kwargs["max_tokens"] == DEFAULT_MAX_TOKENS

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_should_use_provided_string_number(self):
        """get_llm with max_tokens='2048' should use 2048."""
        result = get_llm(
            _make_model_config(),
            user_id=str(uuid4()),
            max_tokens="2048",
        )

        assert result.kwargs["max_tokens"] == 2048

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_should_use_default_when_max_tokens_is_negative(self):
        """get_llm with max_tokens=-1 should use DEFAULT_MAX_TOKENS."""
        result = get_llm(
            _make_model_config(),
            user_id=str(uuid4()),
            max_tokens=-1,
        )

        assert result.kwargs["max_tokens"] == DEFAULT_MAX_TOKENS

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_should_use_provider_specific_field_name(self):
        """get_llm should use the provider-specific max_tokens field name."""
        model = [
            {
                "name": "model",
                "provider": "Custom",
                "metadata": {
                    "model_class": "ChatOpenAI",
                    "api_key_param": "api_key",
                    "model_name_param": "model",
                    "max_tokens_field_name": "max_output_tokens",
                },
            }
        ]
        result = get_llm(
            model,
            user_id=str(uuid4()),
            max_tokens=500,
        )

        assert result.kwargs["max_output_tokens"] == 500
        assert "max_tokens" not in result.kwargs
