"""Unit tests for Agentics model configuration helpers."""

from __future__ import annotations

import pytest

try:
    import agentics  # noqa: F401
    import crewai  # noqa: F401
except ImportError:
    pytest.skip("agentics-py and crewai not installed", allow_module_level=True)

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


@pytest.mark.unit
class TestValidateModelSelection:
    """Tests for validate_model_selection function."""

    def test_should_return_model_and_provider_when_valid_selection(self):
        """Test extraction of model name and provider from valid selection."""
        model = [{"name": "gpt-4", "provider": "OpenAI"}]

        model_name, provider = validate_model_selection(model)

        assert model_name == "gpt-4"
        assert provider == "OpenAI"

    def test_should_raise_when_model_is_none(self):
        """Test that ValueError is raised when model is None."""
        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection(None)

    def test_should_raise_when_model_is_empty_list(self):
        """Test that ValueError is raised when model is empty list."""
        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection([])

    def test_should_raise_when_model_is_not_list(self):
        """Test that ValueError is raised when model is not a list."""
        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection("not-a-list")

    def test_should_raise_when_model_name_missing(self):
        """Test that ValueError is raised when model name is missing."""
        model = [{"provider": "OpenAI"}]

        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection(model)

    def test_should_raise_when_provider_missing(self):
        """Test that ValueError is raised when provider is missing."""
        model = [{"name": "gpt-4"}]

        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection(model)

    def test_should_raise_when_model_name_is_empty_string(self):
        """Test that ValueError is raised when model name is empty string."""
        model = [{"name": "", "provider": "OpenAI"}]

        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection(model)

    def test_should_raise_when_provider_is_empty_string(self):
        """Test that ValueError is raised when provider is empty string."""
        model = [{"name": "gpt-4", "provider": ""}]

        with pytest.raises(ValueError, match=ERROR_MODEL_NOT_SELECTED):
            validate_model_selection(model)


@pytest.mark.unit
class TestUpdateProviderFieldsVisibility:
    """Tests for update_provider_fields_visibility function."""

    def test_should_show_watsonx_fields_when_watsonx_selected(self):
        """Test that WatsonX fields are shown when WatsonX provider is selected."""
        build_config = {
            "model": {"value": [{"name": "model-1", "provider": PROVIDER_IBM_WATSONX}]},
            "base_url_ibm_watsonx": {"show": False, "required": False},
            "project_id": {"show": False, "required": False},
            "ollama_base_url": {"show": True},
        }

        result = update_provider_fields_visibility(build_config, None, None)

        assert result["base_url_ibm_watsonx"]["show"] is True
        assert result["base_url_ibm_watsonx"]["required"] is True
        assert result["project_id"]["show"] is True
        assert result["project_id"]["required"] is True
        assert result["ollama_base_url"]["show"] is False

    def test_should_show_ollama_fields_when_ollama_selected(self):
        """Test that Ollama fields are shown when Ollama provider is selected."""
        build_config = {
            "model": {"value": [{"name": "llama2", "provider": PROVIDER_OLLAMA}]},
            "base_url_ibm_watsonx": {"show": True, "required": True},
            "project_id": {"show": True, "required": True},
            "ollama_base_url": {"show": False},
        }

        result = update_provider_fields_visibility(build_config, None, None)

        assert result["base_url_ibm_watsonx"]["show"] is False
        assert result["base_url_ibm_watsonx"]["required"] is False
        assert result["project_id"]["show"] is False
        assert result["project_id"]["required"] is False
        assert result["ollama_base_url"]["show"] is True

    def test_should_hide_all_provider_fields_when_openai_selected(self):
        """Test that provider-specific fields are hidden when OpenAI is selected."""
        build_config = {
            "model": {"value": [{"name": "gpt-4", "provider": PROVIDER_OPENAI}]},
            "base_url_ibm_watsonx": {"show": True, "required": True},
            "project_id": {"show": True, "required": True},
            "ollama_base_url": {"show": True},
        }

        result = update_provider_fields_visibility(build_config, None, None)

        assert result["base_url_ibm_watsonx"]["show"] is False
        assert result["project_id"]["show"] is False
        assert result["ollama_base_url"]["show"] is False

    def test_should_return_unchanged_when_model_value_is_empty(self):
        """Test that build_config is unchanged when model value is empty."""
        build_config = {
            "model": {"value": []},
            "base_url_ibm_watsonx": {"show": True},
            "project_id": {"show": True},
        }

        result = update_provider_fields_visibility(build_config, None, None)

        assert result["base_url_ibm_watsonx"]["show"] is True
        assert result["project_id"]["show"] is True

    def test_should_return_unchanged_when_model_value_is_not_list(self):
        """Test that build_config is unchanged when model value is not a list."""
        build_config = {
            "model": {"value": "not-a-list"},
            "base_url_ibm_watsonx": {"show": True},
        }

        result = update_provider_fields_visibility(build_config, None, None)

        assert result["base_url_ibm_watsonx"]["show"] is True

    def test_should_use_field_value_when_field_name_is_model(self):
        """Test that field_value is used when field_name is 'model'."""
        build_config = {
            "model": {"value": [{"name": "old-model", "provider": PROVIDER_OPENAI}]},
            "base_url_ibm_watsonx": {"show": False, "required": False},
            "project_id": {"show": False, "required": False},
        }
        field_value = [{"name": "new-model", "provider": PROVIDER_IBM_WATSONX}]

        result = update_provider_fields_visibility(build_config, field_value, "model")

        assert result["base_url_ibm_watsonx"]["show"] is True
        assert result["project_id"]["show"] is True

    def test_should_handle_missing_provider_fields_gracefully(self):
        """Test that function handles missing provider fields without error."""
        build_config = {
            "model": {"value": [{"name": "model-1", "provider": PROVIDER_IBM_WATSONX}]},
        }

        result = update_provider_fields_visibility(build_config, None, None)

        assert "base_url_ibm_watsonx" not in result
        assert "project_id" not in result
