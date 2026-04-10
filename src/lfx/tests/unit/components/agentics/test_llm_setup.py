"""Tests for the LLM setup utility that prepares LLM instances from component settings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from lfx.components.agentics.constants import (
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
)
from lfx.components.agentics.helpers.llm_setup import prepare_llm_from_component

FAKE_API_KEY = "test-api-key-456"
FAKE_MODEL_NAME = "gpt-4"


_DEFAULT_MODEL = [{"name": FAKE_MODEL_NAME, "provider": PROVIDER_OPENAI}]


def _create_mock_component(
    model: list | None = None,
    api_key: str = "",
    user_id: str = "test-user",
) -> MagicMock:
    """Create a mock component with standard attributes."""
    component = MagicMock()
    component.model = _DEFAULT_MODEL if model is None else model
    component.api_key = api_key
    component.user_id = user_id
    return component


class TestPrepareLlmFromComponent:
    """Tests for prepare_llm_from_component function."""

    @patch("lfx.components.agentics.helpers.llm_setup.create_llm")
    @patch("lfx.components.agentics.helpers.llm_setup.get_api_key_for_provider")
    def test_should_create_llm_with_resolved_api_key(
        self,
        mock_get_api_key: MagicMock,
        mock_create_llm: MagicMock,
    ):
        # Arrange
        mock_get_api_key.return_value = FAKE_API_KEY
        component = _create_mock_component()

        # Act
        prepare_llm_from_component(component)

        # Assert
        mock_get_api_key.assert_called_once_with("test-user", PROVIDER_OPENAI, "")
        mock_create_llm.assert_called_once_with(
            provider=PROVIDER_OPENAI,
            model_name=FAKE_MODEL_NAME,
            api_key=FAKE_API_KEY,
            base_url_ibm_watsonx=component.base_url_ibm_watsonx,
            project_id=component.project_id,
            ollama_base_url=component.ollama_base_url,
        )

    @patch("lfx.components.agentics.helpers.llm_setup.create_llm")
    @patch("lfx.components.agentics.helpers.llm_setup.get_api_key_for_provider")
    def test_should_raise_when_api_key_missing_for_non_ollama_provider(
        self,
        mock_get_api_key: MagicMock,
        mock_create_llm: MagicMock,
    ):
        # Arrange
        mock_get_api_key.return_value = None
        component = _create_mock_component()

        # Act & Assert
        with pytest.raises(ValueError, match=PROVIDER_OPENAI):
            prepare_llm_from_component(component)

        mock_create_llm.assert_not_called()

    @patch("lfx.components.agentics.helpers.llm_setup.create_llm")
    @patch("lfx.components.agentics.helpers.llm_setup.get_api_key_for_provider")
    def test_should_allow_no_api_key_for_ollama_provider(
        self,
        mock_get_api_key: MagicMock,
        mock_create_llm: MagicMock,
    ):
        # Arrange
        mock_get_api_key.return_value = None
        component = _create_mock_component(
            model=[{"name": "llama3", "provider": PROVIDER_OLLAMA}],
        )

        # Act
        prepare_llm_from_component(component)

        # Assert
        mock_create_llm.assert_called_once()
        call_kwargs = mock_create_llm.call_args[1]
        assert call_kwargs["api_key"] is None
        assert call_kwargs["provider"] == PROVIDER_OLLAMA

    @patch("lfx.components.agentics.helpers.llm_setup.create_llm")
    def test_should_raise_when_model_not_selected(
        self,
        mock_create_llm: MagicMock,
    ):
        # Arrange
        component = _create_mock_component(model=[])

        # Act & Assert
        with pytest.raises(ValueError, match="No model selected"):
            prepare_llm_from_component(component)

        mock_create_llm.assert_not_called()
