"""Unit tests for Agentics LLM setup helper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

try:
    import agentics  # noqa: F401
    import crewai  # noqa: F401
except ImportError:
    pytest.skip("agentics-py and crewai not installed", allow_module_level=True)

from lfx.components.agentics.constants import (
    PROVIDER_ANTHROPIC,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
)


@pytest.fixture
def mock_component():
    """Create a mock component with required attributes."""
    component = MagicMock()
    component.model = [{"name": "gpt-4", "provider": PROVIDER_OPENAI}]
    component.api_key = "test-api-key"
    component.user_id = "test-user-id"
    component.base_url_ibm_watsonx = None
    component.project_id = None
    component.ollama_base_url = None
    return component


@pytest.mark.unit
class TestPrepareLlmFromComponent:
    """Tests for prepare_llm_from_component function."""

    @patch("lfx.components.agentics.helpers.llm_setup.create_llm")
    @patch("lfx.components.agentics.helpers.llm_setup.get_api_key_for_provider")
    @patch("lfx.components.agentics.helpers.llm_setup.validate_model_selection")
    def test_should_call_validate_model_selection_with_component_model(
        self, mock_validate, mock_get_api_key, mock_create_llm, mock_component
    ):
        """Test that validate_model_selection is called with component.model."""
        from lfx.components.agentics.helpers.llm_setup import prepare_llm_from_component

        mock_validate.return_value = ("gpt-4", PROVIDER_OPENAI)
        mock_get_api_key.return_value = "test-api-key"
        mock_create_llm.return_value = MagicMock()

        prepare_llm_from_component(mock_component)

        mock_validate.assert_called_once_with(mock_component.model)

    @patch("lfx.components.agentics.helpers.llm_setup.create_llm")
    @patch("lfx.components.agentics.helpers.llm_setup.get_api_key_for_provider")
    @patch("lfx.components.agentics.helpers.llm_setup.validate_model_selection")
    def test_should_call_get_api_key_for_provider_with_correct_params(
        self, mock_validate, mock_get_api_key, mock_create_llm, mock_component
    ):
        """Test that get_api_key_for_provider is called with correct parameters."""
        from lfx.components.agentics.helpers.llm_setup import prepare_llm_from_component

        mock_validate.return_value = ("gpt-4", PROVIDER_OPENAI)
        mock_get_api_key.return_value = "resolved-api-key"
        mock_create_llm.return_value = MagicMock()

        prepare_llm_from_component(mock_component)

        mock_get_api_key.assert_called_once_with(mock_component.user_id, PROVIDER_OPENAI, mock_component.api_key)

    @patch("lfx.components.agentics.helpers.llm_setup.create_llm")
    @patch("lfx.components.agentics.helpers.llm_setup.get_api_key_for_provider")
    @patch("lfx.components.agentics.helpers.llm_setup.validate_model_selection")
    def test_should_call_create_llm_with_all_params(
        self, mock_validate, mock_get_api_key, mock_create_llm, mock_component
    ):
        """Test that create_llm is called with all component parameters."""
        from lfx.components.agentics.helpers.llm_setup import prepare_llm_from_component

        mock_validate.return_value = ("gpt-4", PROVIDER_OPENAI)
        mock_get_api_key.return_value = "resolved-api-key"
        mock_llm = MagicMock()
        mock_create_llm.return_value = mock_llm

        mock_component.base_url_ibm_watsonx = "https://watsonx.url"
        mock_component.project_id = "project-123"
        mock_component.ollama_base_url = "http://ollama:11434"

        result = prepare_llm_from_component(mock_component)

        mock_create_llm.assert_called_once_with(
            provider=PROVIDER_OPENAI,
            model_name="gpt-4",
            api_key="resolved-api-key",
            base_url_ibm_watsonx="https://watsonx.url",
            project_id="project-123",
            ollama_base_url="http://ollama:11434",
        )
        assert result == mock_llm

    @patch("lfx.components.agentics.helpers.llm_setup.get_api_key_for_provider")
    @patch("lfx.components.agentics.helpers.llm_setup.validate_model_selection")
    def test_should_raise_when_api_key_missing_for_cloud_provider(
        self, mock_validate, mock_get_api_key, mock_component
    ):
        """Test that ValueError is raised when API key is missing for cloud provider."""
        from lfx.components.agentics.helpers.llm_setup import prepare_llm_from_component

        mock_validate.return_value = ("gpt-4", PROVIDER_OPENAI)
        mock_get_api_key.return_value = None

        with pytest.raises(ValueError, match="API key is required"):
            prepare_llm_from_component(mock_component)

    @patch("lfx.components.agentics.helpers.llm_setup.create_llm")
    @patch("lfx.components.agentics.helpers.llm_setup.get_api_key_for_provider")
    @patch("lfx.components.agentics.helpers.llm_setup.validate_model_selection")
    def test_should_not_raise_when_api_key_missing_for_ollama(
        self, mock_validate, mock_get_api_key, mock_create_llm, mock_component
    ):
        """Test that no error is raised when API key is missing for Ollama."""
        from lfx.components.agentics.helpers.llm_setup import prepare_llm_from_component

        mock_validate.return_value = ("llama2", PROVIDER_OLLAMA)
        mock_get_api_key.return_value = None
        mock_llm = MagicMock()
        mock_create_llm.return_value = mock_llm

        result = prepare_llm_from_component(mock_component)

        assert result == mock_llm
        mock_create_llm.assert_called_once()

    @patch("lfx.components.agentics.helpers.llm_setup.create_llm")
    @patch("lfx.components.agentics.helpers.llm_setup.get_api_key_for_provider")
    @patch("lfx.components.agentics.helpers.llm_setup.validate_model_selection")
    def test_should_handle_missing_optional_attributes(self, mock_validate, mock_get_api_key, mock_create_llm):
        """Test handling of component without optional attributes."""
        from lfx.components.agentics.helpers.llm_setup import prepare_llm_from_component

        component = MagicMock(spec=["model", "api_key", "user_id"])
        component.model = [{"name": "claude-3", "provider": PROVIDER_ANTHROPIC}]
        component.api_key = "test-key"
        component.user_id = "user-123"

        mock_validate.return_value = ("claude-3", PROVIDER_ANTHROPIC)
        mock_get_api_key.return_value = "test-key"
        mock_create_llm.return_value = MagicMock()

        prepare_llm_from_component(component)

        call_kwargs = mock_create_llm.call_args[1]
        assert call_kwargs["base_url_ibm_watsonx"] is None
        assert call_kwargs["project_id"] is None
        assert call_kwargs["ollama_base_url"] is None
