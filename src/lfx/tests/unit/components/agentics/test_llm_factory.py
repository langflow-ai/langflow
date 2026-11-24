"""Tests for the LLM factory that creates provider-specific LLM instances."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
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
from lfx.components.agentics.helpers.llm_factory import create_llm

FAKE_API_KEY = "test-api-key-123"
FAKE_MODEL_NAME = "test-model"


@pytest.fixture
def mock_crewai_llm():
    """Mock the crewai module so tests don't require it installed."""
    mock_crewai = MagicMock()
    mock_llm_class = MagicMock()
    mock_crewai.LLM = mock_llm_class
    with patch.dict(sys.modules, {"crewai": mock_crewai}):
        yield mock_llm_class


class TestCreateLlm:
    """Tests for create_llm factory function."""

    def test_should_create_openai_llm_with_correct_prefix(self, mock_crewai_llm: MagicMock):
        # Act
        create_llm(PROVIDER_OPENAI, FAKE_MODEL_NAME, FAKE_API_KEY)

        # Assert
        mock_crewai_llm.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_OPENAI] + FAKE_MODEL_NAME,
            api_key=FAKE_API_KEY,
        )

    def test_should_create_anthropic_llm_with_correct_prefix(self, mock_crewai_llm: MagicMock):
        # Act
        create_llm(PROVIDER_ANTHROPIC, FAKE_MODEL_NAME, FAKE_API_KEY)

        # Assert
        mock_crewai_llm.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_ANTHROPIC] + FAKE_MODEL_NAME,
            api_key=FAKE_API_KEY,
        )

    def test_should_create_google_llm_with_correct_prefix(self, mock_crewai_llm: MagicMock):
        # Act
        create_llm(PROVIDER_GOOGLE, FAKE_MODEL_NAME, FAKE_API_KEY)

        # Assert
        mock_crewai_llm.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_GOOGLE] + FAKE_MODEL_NAME,
            api_key=FAKE_API_KEY,
        )

    def test_should_create_watsonx_llm_with_defaults(self, mock_crewai_llm: MagicMock):
        # Arrange
        base_url = "https://us-south.ml.cloud.ibm.com"
        project_id = "test-project-123"

        # Act
        create_llm(
            PROVIDER_IBM_WATSONX,
            FAKE_MODEL_NAME,
            FAKE_API_KEY,
            base_url_ibm_watsonx=base_url,
            project_id=project_id,
        )

        # Assert
        mock_crewai_llm.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_IBM_WATSONX] + FAKE_MODEL_NAME,
            base_url=base_url,
            project_id=project_id,
            api_key=FAKE_API_KEY,
            temperature=WATSONX_DEFAULT_TEMPERATURE,
            max_tokens=WATSONX_DEFAULT_MAX_TOKENS,
            max_input_tokens=WATSONX_DEFAULT_MAX_INPUT_TOKENS,
        )

    def test_should_create_ollama_llm_with_custom_url(self, mock_crewai_llm: MagicMock):
        # Arrange
        custom_url = "http://my-server:11434"

        # Act
        create_llm(PROVIDER_OLLAMA, FAKE_MODEL_NAME, None, ollama_base_url=custom_url)

        # Assert
        mock_crewai_llm.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_OLLAMA] + FAKE_MODEL_NAME,
            base_url=custom_url,
        )

    def test_should_use_default_ollama_url_when_none_provided(self, mock_crewai_llm: MagicMock):
        # Act
        create_llm(PROVIDER_OLLAMA, FAKE_MODEL_NAME, None)

        # Assert
        mock_crewai_llm.assert_called_once_with(
            model=LLM_MODEL_PREFIXES[PROVIDER_OLLAMA] + FAKE_MODEL_NAME,
            base_url=DEFAULT_OLLAMA_URL,
        )

    def test_should_raise_value_error_for_unsupported_provider(self, mock_crewai_llm: MagicMock):
        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported provider"):
            create_llm("UnknownProvider", FAKE_MODEL_NAME, FAKE_API_KEY)

        mock_crewai_llm.assert_not_called()
