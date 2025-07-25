from unittest.mock import MagicMock, patch

import pytest
from langflow.components.nvidia.nemo_guardrails import NVIDIANeMoGuardrailsComponent

from tests.base import ComponentTestBaseWithoutClient
from tests.unit.mock_language_model import MockLanguageModel


class TestNVIDIANeMoGuardrailsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return NVIDIANeMoGuardrailsComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "llm": MockLanguageModel(),
            "rails": ["self check input", "self check output"],
            "self_check_model_url": "https://test.api.nvidia.com/v1",
            "self_check_model_api_key": "test_key",
            "self_check_model_name": "openai/gpt-3.5-turbo-instruct",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    def test_component_initialization(self, component_class):
        """Test that the component initializes with correct default values."""
        component = component_class()
        assert component.display_name == "NeMo Guardrails"
        assert component.description is not None
        assert component.icon == "NVIDIA"
        assert component.name == "NVIDIANemoGuardrails"
        assert component.beta is True

    def test_generate_rails_config(self, component_class, default_kwargs):
        """Test YAML configuration generation with different rail combinations."""
        component = component_class(**default_kwargs)

        # Test with default rails
        config = component.generate_rails_config()
        assert "models" in config
        assert "rails" in config
        assert "self check input" in config

        # Test with custom YAML content
        custom_yaml = "models: []\nrails: {}\n"
        component.yaml_content = custom_yaml
        config = component.generate_rails_config()
        assert config == custom_yaml

    @patch("langflow.components.nvidia.nemo_guardrails.RailsConfig")
    @patch("langflow.components.nvidia.nemo_guardrails.RunnableRails")
    def test_build_model(self, mock_runnable_rails, component_class, default_kwargs):
        """Test model building with different configurations."""
        component = component_class(**default_kwargs)

        # Test with default configuration
        mock_instance = MagicMock()
        mock_runnable_rails.return_value = mock_instance
        model = component.build_model()
        assert model is not None

        # Test with verbose logging
        component.guardrails_verbose = True
        model = component.build_model()
        assert model is not None

    @patch("requests.get")
    def test_get_models(self, mock_get, component_class, default_kwargs):
        """Test retrieval of available models from NVIDIA API."""
        component = component_class(**default_kwargs)

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"id": "openai/gpt-3.5-turbo-instruct"}, {"id": "anthropic/claude-3-opus-20240229"}]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        models = component.get_models()
        assert len(models) > 0
        assert "openai/gpt-3.5-turbo-instruct" in models

    def test_update_build_config(self, component_class, default_kwargs):
        """Test updating build configuration with model list."""
        component = component_class(**default_kwargs)
        build_config = {"self_check_model_name": {"options": [], "value": ""}}

        with patch.object(component, "get_models", return_value=["model1", "model2"]):
            updated_config = component.update_build_config(build_config, "test_key", "self_check_model_api_key")
            assert len(updated_config["self_check_model_name"]["options"]) == 2

    def test_error_handling(self, component_class, default_kwargs):
        """Test error handling in various scenarios."""
        component = component_class(**default_kwargs)

        # Test invalid YAML content
        component.yaml_content = "invalid: yaml: content:"
        with pytest.raises(ValueError, match="Invalid YAML syntax"):
            component.build_model()

        # Test missing API key
        component.self_check_model_api_key = None
        # Should return an empty list, not raise
        assert component.get_models() == []

    def test_required_urls_for_rails(self, component_class, default_kwargs):
        """Test that required URLs are set when corresponding rails are enabled."""
        component = component_class(**default_kwargs)

        # Test self check rails
        component.rails = ["self check input"]
        component.self_check_model_url = ""
        with pytest.raises(ValueError, match="self_check_model_url must be set when self check rails are enabled"):
            component.build_model()

        # Test topic control rails
        component.rails = ["topic control"]
        component.topic_control_model_url = ""
        with pytest.raises(
            ValueError, match="topic_control_model_url must be set when topic control rails are enabled"
        ):
            component.build_model()

        # Test content safety rails
        component.rails = ["content safety input"]
        component.content_safety_model_url = ""
        with pytest.raises(
            ValueError, match="content_safety_model_url must be set when content safety rails are enabled"
        ):
            component.build_model()

        # Test jailbreak detection rails
        component.rails = ["jailbreak detection model"]
        component.jailbreak_detection_model_url = ""
        with pytest.raises(
            ValueError, match="jailbreak_detection_model_url must be set when jailbreak detection rails are enabled"
        ):
            component.build_model()
