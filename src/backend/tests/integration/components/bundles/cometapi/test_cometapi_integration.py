import os
from unittest.mock import MagicMock, patch

import pytest
from lfx.components.cometapi.cometapi import CometAPIComponent


class TestCometAPIIntegration:
    """Integration tests for CometAPI component."""

    @pytest.fixture
    def component(self):
        """Create a CometAPI component instance for testing."""
        return CometAPIComponent()

    @pytest.fixture
    def mock_api_key(self):
        """Mock API key for testing."""
        return "test-cometapi-key"

    def test_component_import(self):
        """Test that the CometAPI component can be imported."""
        from lfx.components.cometapi.cometapi import CometAPIComponent

        assert CometAPIComponent is not None

    def test_component_instantiation(self, component):
        """Test that the component can be instantiated."""
        assert component is not None
        assert component.display_name == "CometAPI"
        assert component.name == "CometAPIModel"

    def test_component_inputs_present(self, component):
        """Test that all expected inputs are present."""
        input_names = [input_.name for input_ in component.inputs]

        expected_inputs = [
            "api_key",
            "app_name",
            "model_name",
            "model_kwargs",
            "temperature",
            "max_tokens",
            "seed",
            "json_mode",
        ]

        for expected_input in expected_inputs:
            assert expected_input in input_names

    @patch("requests.get")
    def test_model_fetching_integration(self, mock_get, component, mock_api_key):
        """Test the complete model fetching flow."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"id": "gpt-4o-mini"}, {"id": "claude-3-5-haiku-latest"}, {"id": "gemini-2.5-flash"}]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Set API key
        component.set_attributes({"api_key": mock_api_key})

        # Fetch models
        models = component.get_models()

        # Verify results
        assert models == ["gpt-4o-mini", "claude-3-5-haiku-latest", "gemini-2.5-flash"]
        mock_get.assert_called_once()

    @patch("lfx.components.cometapi.cometapi.ChatOpenAI")
    def test_model_building_integration(self, mock_chat_openai, component, mock_api_key):
        """Test the complete model building flow."""
        # Mock ChatOpenAI
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        # Configure component
        component.set_attributes(
            {
                "api_key": mock_api_key,
                "model_name": "gpt-4o-mini",
                "temperature": 0.7,
                "max_tokens": 1000,
                "seed": 42,
                "json_mode": False,
            }
        )

        # Build model
        model = component.build_model()

        # Verify ChatOpenAI was called correctly
        assert mock_chat_openai.call_count == 1
        _args, kwargs = mock_chat_openai.call_args
        assert kwargs["model"] == "gpt-4o-mini"
        assert kwargs["api_key"] == "test-cometapi-key"
        assert kwargs["max_tokens"] == 1000
        assert kwargs["temperature"] == 0.7
        assert kwargs["model_kwargs"] == {}
        # streaming defaults to None when not explicitly set
        assert kwargs.get("streaming") in (None, False)
        assert kwargs["seed"] == 42
        assert kwargs["base_url"] == "https://api.cometapi.com/v1"
        assert model == mock_instance

    @patch("lfx.components.cometapi.cometapi.ChatOpenAI")
    def test_json_mode_integration(self, mock_chat_openai, component, mock_api_key):
        """Test JSON mode integration."""
        # Mock ChatOpenAI and bind method
        mock_instance = MagicMock()
        mock_bound_instance = MagicMock()
        mock_instance.bind.return_value = mock_bound_instance
        mock_chat_openai.return_value = mock_instance

        # Configure component with JSON mode
        component.set_attributes({"api_key": mock_api_key, "model_name": "gpt-4o-mini", "json_mode": True})

        # Build model
        model = component.build_model()

        # Verify JSON mode binding
        mock_instance.bind.assert_called_once_with(response_format={"type": "json_object"})
        assert model == mock_bound_instance

    def test_error_handling_integration(self, component):
        """Test error handling in integration scenarios."""
        # Test with invalid model name
        component.set_attributes({"model_name": "Select a model"})

        with pytest.raises(ValueError, match="Please select a valid CometAPI model"):
            component.build_model()

    @patch("requests.get")
    def test_fallback_behavior_integration(self, mock_get, component):
        """Test fallback behavior when API is unavailable."""
        # Mock API failure
        import requests

        mock_get.side_effect = requests.RequestException("Network error")

        # Should fallback to constants
        models = component.get_models()

        # Should return fallback models
        from lfx.base.models.cometapi_constants import MODEL_NAMES

        assert models == MODEL_NAMES
        assert "Error fetching models" in component.status

    def test_update_build_config_integration(self, component):
        """Test update_build_config integration."""
        build_config = {"model_name": {"value": "current-model", "placeholder": "Select a model"}}

        with patch.object(component, "get_models", return_value=["gpt-4o-mini", "claude-3-5-haiku-latest"]):
            updated_config = component.update_build_config(build_config, "new-key", "api_key")

        # Verify config was updated
        assert "model_name" in updated_config
        model_config = updated_config["model_name"]
        assert "gpt-4o-mini" in model_config["options"]
        assert "claude-3-5-haiku-latest" in model_config["options"]

    @pytest.mark.skipif(os.getenv("COMETAPI_KEY") is None, reason="COMETAPI_KEY not set")
    def test_real_api_integration(self, component):
        """Test with real API key if available."""
        component.set_attributes(
            {"api_key": os.getenv("COMETAPI_KEY"), "model_name": "gpt-4o-mini", "temperature": 0.1, "max_tokens": 50}
        )

        # Test model building
        model = component.build_model()
        assert model is not None

        # Test model fetching
        models = component.get_models()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_component_serialization(self, component):
        """Test that component can be serialized/deserialized."""
        # Set some values
        component.set_attributes({"api_key": "test-key", "model_name": "gpt-4o-mini", "temperature": 0.5})

        # Test that component attributes are accessible
        assert component.api_key == "test-key"
        assert component.model_name == "gpt-4o-mini"
        assert component.temperature == 0.5

    def test_component_validation(self, component):
        """Test component input validation."""
        # Test with valid inputs
        component.set_attributes(
            {"api_key": "valid-key", "model_name": "gpt-4o-mini", "temperature": 0.7, "max_tokens": 1000}
        )

        # Should not raise any validation errors
        assert component.api_key is not None
        assert component.model_name is not None

    def test_component_defaults(self, component):
        """Test component default values."""
        # Check that component has reasonable defaults
        assert component.temperature == 0.7
        assert component.seed == 1
        assert component.json_mode is False
        assert component.model_kwargs == {}
