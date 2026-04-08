"""Tests for model configuration and validation helpers."""

from __future__ import annotations

import pytest
from lfx.components.agentics.constants import (
    ERROR_MODEL_NOT_SELECTED,
    PROVIDER_IBM_WATSONX,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
)
from lfx.components.agentics.helpers.model_config import (
    update_provider_fields_visibility,
    validate_model_selection,
)


class TestValidateModelSelection:
    """Tests for validate_model_selection function."""

    def test_should_return_model_name_and_provider_when_valid(self):
        # Arrange
        model = [{"name": "gpt-4", "provider": "OpenAI"}]

        # Act
        model_name, provider = validate_model_selection(model)

        # Assert
        assert model_name == "gpt-4"
        assert provider == "OpenAI"

    def test_should_raise_value_error_when_model_is_none(self):
        # Act & Assert
        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection(None)

    def test_should_raise_value_error_when_model_is_empty_list(self):
        # Act & Assert
        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection([])

    def test_should_raise_value_error_when_model_is_not_a_list(self):
        # Act & Assert
        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection("gpt-4")

    def test_should_raise_value_error_when_name_is_missing(self):
        # Arrange
        model = [{"provider": "OpenAI"}]

        # Act & Assert
        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection(model)

    def test_should_raise_value_error_when_provider_is_missing(self):
        # Arrange
        model = [{"name": "gpt-4"}]

        # Act & Assert
        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection(model)

    def test_should_raise_value_error_when_name_is_empty_string(self):
        # Arrange
        model = [{"name": "", "provider": "OpenAI"}]

        # Act & Assert
        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection(model)

    def test_should_use_first_element_when_multiple_models_provided(self):
        # Arrange
        model = [
            {"name": "gpt-4", "provider": "OpenAI"},
            {"name": "claude-3", "provider": "Anthropic"},
        ]

        # Act
        model_name, provider = validate_model_selection(model)

        # Assert
        assert model_name == "gpt-4"
        assert provider == "OpenAI"


class TestUpdateProviderFieldsVisibility:
    """Tests for update_provider_fields_visibility function."""

    def _create_build_config(self) -> dict:
        """Create a minimal build_config with provider-specific fields."""
        return {
            "model": {"value": []},
            "base_url_ibm_watsonx": {"show": False, "required": False},
            "project_id": {"show": False, "required": False},
            "ollama_base_url": {"show": False},
        }

    def test_should_show_watsonx_fields_when_watsonx_selected(self):
        # Arrange
        build_config = self._create_build_config()
        field_value = [{"name": "granite-3", "provider": PROVIDER_IBM_WATSONX}]

        # Act
        result = update_provider_fields_visibility(build_config, field_value, "model")

        # Assert
        assert result["base_url_ibm_watsonx"]["show"] is True
        assert result["base_url_ibm_watsonx"]["required"] is True
        assert result["project_id"]["show"] is True
        assert result["project_id"]["required"] is True
        assert result["ollama_base_url"]["show"] is False

    def test_should_show_ollama_fields_when_ollama_selected(self):
        # Arrange
        build_config = self._create_build_config()
        field_value = [{"name": "llama3", "provider": PROVIDER_OLLAMA}]

        # Act
        result = update_provider_fields_visibility(build_config, field_value, "model")

        # Assert
        assert result["ollama_base_url"]["show"] is True
        assert result["base_url_ibm_watsonx"]["show"] is False
        assert result["project_id"]["show"] is False

    def test_should_hide_all_provider_fields_when_openai_selected(self):
        # Arrange
        build_config = self._create_build_config()
        field_value = [{"name": "gpt-4", "provider": PROVIDER_OPENAI}]

        # Act
        result = update_provider_fields_visibility(build_config, field_value, "model")

        # Assert
        assert result["base_url_ibm_watsonx"]["show"] is False
        assert result["project_id"]["show"] is False
        assert result["ollama_base_url"]["show"] is False

    def test_should_return_config_unchanged_when_field_value_is_empty_list(self):
        # Arrange
        build_config = self._create_build_config()

        # Act
        result = update_provider_fields_visibility(build_config, [], "model")

        # Assert
        assert result["base_url_ibm_watsonx"]["show"] is False
        assert result["ollama_base_url"]["show"] is False

    def test_should_return_config_unchanged_when_field_value_is_not_list(self):
        # Arrange
        build_config = self._create_build_config()

        # Act
        result = update_provider_fields_visibility(build_config, "not-a-list", "model")

        # Assert
        assert result["base_url_ibm_watsonx"]["show"] is False

    def test_should_read_from_build_config_when_field_name_is_not_model(self):
        # Arrange
        build_config = self._create_build_config()
        build_config["model"]["value"] = [{"name": "llama3", "provider": PROVIDER_OLLAMA}]

        # Act
        result = update_provider_fields_visibility(build_config, "some-api-key", "api_key")

        # Assert
        assert result["ollama_base_url"]["show"] is True
