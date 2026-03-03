"""Unit tests for Agentics LLM factory."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

try:
    import agentics  # noqa: F401
    import crewai  # noqa: F401
except ImportError:
    pytest.skip("agentics-py and crewai not installed", allow_module_level=True)

from lfx.components.agentics.constants import (
    DEFAULT_OLLAMA_URL,
    LLM_MODEL_PREFIXES,
    PROVIDER_ANTHROPIC,
    PROVIDER_GOOGLE,
    PROVIDER_IBM_WATSONX,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    WATSONX_DEFAULT_MAX_INPUT_TOKENS,
    WATSONX_DEFAULT_MAX_TOKENS,
    WATSONX_DEFAULT_TEMPERATURE,
)


@pytest.fixture
def mock_crewai():
    """Mock the crewai module for testing."""
    mock_llm_class = MagicMock()
    mock_module = MagicMock()
    mock_module.LLM = mock_llm_class
    with patch.dict(sys.modules, {"crewai": mock_module}):
        yield mock_llm_class


@pytest.mark.unit
class TestCreateLlm:
    """Tests for create_llm factory function."""

    def test_should_create_openai_llm_with_correct_params(self, mock_crewai):
        """Test OpenAI LLM creation with correct model prefix and API key."""
        from lfx.components.agentics.helpers.llm_factory import create_llm

        mock_llm = MagicMock()
        mock_crewai.return_value = mock_llm

        result = create_llm(
            provider=PROVIDER_OPENAI,
            model_name="gpt-4",
            api_key="test-api-key",
        )

        mock_crewai.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_OPENAI] + "gpt-4",
            api_key="test-api-key",
        )
        assert result == mock_llm

    def test_should_create_google_llm_with_correct_params(self, mock_crewai):
        """Test Google LLM creation with correct model prefix and API key."""
        from lfx.components.agentics.helpers.llm_factory import create_llm

        mock_llm = MagicMock()
        mock_crewai.return_value = mock_llm

        result = create_llm(
            provider=PROVIDER_GOOGLE,
            model_name="gemini-pro",
            api_key="test-api-key",
        )

        mock_crewai.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_GOOGLE] + "gemini-pro",
            api_key="test-api-key",
        )
        assert result == mock_llm

    def test_should_create_anthropic_llm_with_correct_params(self, mock_crewai):
        """Test Anthropic LLM creation with correct model prefix and API key."""
        from lfx.components.agentics.helpers.llm_factory import create_llm

        mock_llm = MagicMock()
        mock_crewai.return_value = mock_llm

        result = create_llm(
            provider=PROVIDER_ANTHROPIC,
            model_name="claude-3-opus",
            api_key="test-api-key",
        )

        mock_crewai.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_ANTHROPIC] + "claude-3-opus",
            api_key="test-api-key",
        )
        assert result == mock_llm

    @patch(
        "lfx.components.agentics.helpers.llm_factory.IBM_WATSONX_URLS",
        ["https://default.watsonx.url"],
    )
    def test_should_create_watsonx_llm_with_all_params(self, mock_crewai):
        """Test WatsonX LLM creation with all required parameters."""
        from lfx.components.agentics.helpers.llm_factory import create_llm

        mock_llm = MagicMock()
        mock_crewai.return_value = mock_llm

        result = create_llm(
            provider=PROVIDER_IBM_WATSONX,
            model_name="granite-13b",
            api_key="test-api-key",
            base_url_ibm_watsonx="https://custom.watsonx.url",
            project_id="test-project-id",
        )

        mock_crewai.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_IBM_WATSONX] + "granite-13b",
            base_url="https://custom.watsonx.url",
            project_id="test-project-id",
            api_key="test-api-key",
            temperature=WATSONX_DEFAULT_TEMPERATURE,
            max_tokens=WATSONX_DEFAULT_MAX_TOKENS,
            max_input_tokens=WATSONX_DEFAULT_MAX_INPUT_TOKENS,
        )
        assert result == mock_llm

    @patch(
        "lfx.components.agentics.helpers.llm_factory.IBM_WATSONX_URLS",
        ["https://default.watsonx.url"],
    )
    def test_should_use_default_watsonx_url_when_not_provided(self, mock_crewai):
        """Test WatsonX LLM uses default URL when base_url not provided."""
        from lfx.components.agentics.helpers.llm_factory import create_llm

        mock_llm = MagicMock()
        mock_crewai.return_value = mock_llm

        create_llm(
            provider=PROVIDER_IBM_WATSONX,
            model_name="granite-13b",
            api_key="test-api-key",
        )

        call_kwargs = mock_crewai.call_args[1]
        assert call_kwargs["base_url"] == "https://default.watsonx.url"

    def test_should_create_ollama_llm_with_custom_url(self, mock_crewai):
        """Test Ollama LLM creation with custom base URL."""
        from lfx.components.agentics.helpers.llm_factory import create_llm

        mock_llm = MagicMock()
        mock_crewai.return_value = mock_llm

        result = create_llm(
            provider=PROVIDER_OLLAMA,
            model_name="llama2",
            api_key=None,
            ollama_base_url="http://custom.ollama:11434",
        )

        mock_crewai.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_OLLAMA] + "llama2",
            base_url="http://custom.ollama:11434",
        )
        assert result == mock_llm

    def test_should_use_default_ollama_url_when_not_provided(self, mock_crewai):
        """Test Ollama LLM uses default URL when ollama_base_url not provided."""
        from lfx.components.agentics.helpers.llm_factory import create_llm

        mock_llm = MagicMock()
        mock_crewai.return_value = mock_llm

        create_llm(
            provider=PROVIDER_OLLAMA,
            model_name="llama2",
            api_key=None,
        )

        call_kwargs = mock_crewai.call_args[1]
        assert call_kwargs["base_url"] == DEFAULT_OLLAMA_URL

    def test_should_raise_when_provider_not_supported(self, mock_crewai):
        """Test that ValueError is raised for unsupported provider."""
        from lfx.components.agentics.helpers.llm_factory import create_llm

        _ = mock_crewai  # Ensure crewai module is mocked

        with pytest.raises(ValueError, match="UnsupportedProvider"):
            create_llm(
                provider="UnsupportedProvider",
                model_name="some-model",
                api_key="test-key",
            )

    def test_should_handle_none_api_key_for_cloud_providers(self, mock_crewai):
        """Test that cloud providers accept None API key (may fail at runtime)."""
        from lfx.components.agentics.helpers.llm_factory import create_llm

        mock_llm = MagicMock()
        mock_crewai.return_value = mock_llm

        result = create_llm(
            provider=PROVIDER_OPENAI,
            model_name="gpt-4",
            api_key=None,
        )

        mock_crewai.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_OPENAI] + "gpt-4",
            api_key=None,
        )
        assert result == mock_llm
