import os
from unittest.mock import MagicMock, patch

import pytest
from lfx.components.empiriolabs.empiriolabs import EmpirioLabsModelComponent


class TestEmpirioLabsIntegration:
    """Integration tests for EmpirioLabs component."""

    @pytest.fixture
    def component(self):
        """Create an EmpirioLabs component instance for testing."""
        return EmpirioLabsModelComponent()

    @pytest.fixture
    def mock_api_key(self):
        """Mock API key for testing."""
        return "test-empiriolabs-key"

    def test_component_import(self):
        """Test that the EmpirioLabs component can be imported."""
        from lfx.components.empiriolabs.empiriolabs import EmpirioLabsModelComponent

        assert EmpirioLabsModelComponent is not None

    def test_component_instantiation(self, component):
        """Test that the component can be instantiated."""
        assert component is not None
        assert component.display_name == "EmpirioLabs"
        assert component.name == "EmpirioLabsModel"

    def test_component_inputs_present(self, component):
        """Test that all expected inputs are present."""
        input_names = [input_.name for input_ in component.inputs]

        expected_inputs = [
            "api_key",
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
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"id": "qwen3-7-plus"}, {"id": "deepseek-v4-pro"}, {"id": "glm-5-1"}]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        component.set_attributes({"api_key": mock_api_key})

        models = component.get_models()

        assert models == ["qwen3-7-plus", "deepseek-v4-pro", "glm-5-1"]
        mock_get.assert_called_once()

    @patch("lfx.components.empiriolabs.empiriolabs.ChatOpenAI")
    def test_model_building_integration(self, mock_chat_openai, component, mock_api_key):
        """Test the complete model building flow."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        component.set_attributes(
            {
                "api_key": mock_api_key,
                "model_name": "qwen3-7-plus",
                "temperature": 0.1,
                "max_tokens": 1000,
                "seed": 42,
                "json_mode": False,
                "model_kwargs": {},
                "stream": False,
            }
        )

        model = component.build_model()

        assert mock_chat_openai.call_count == 1
        _args, kwargs = mock_chat_openai.call_args
        assert kwargs["model"] == "qwen3-7-plus"
        assert kwargs["api_key"] == "test-empiriolabs-key"
        assert kwargs["max_tokens"] == 1000
        assert kwargs["temperature"] == 0.1
        assert kwargs["model_kwargs"] == {}
        assert kwargs["seed"] == 42
        assert kwargs["base_url"] == "https://api.empiriolabs.ai/v1"
        assert model == mock_instance

    @patch("lfx.components.empiriolabs.empiriolabs.ChatOpenAI")
    def test_json_mode_integration(self, mock_chat_openai, component, mock_api_key):
        """Test JSON mode integration."""
        mock_instance = MagicMock()
        mock_bound_instance = MagicMock()
        mock_instance.bind.return_value = mock_bound_instance
        mock_chat_openai.return_value = mock_instance

        component.set_attributes(
            {
                "api_key": mock_api_key,
                "model_name": "qwen3-7-plus",
                "json_mode": True,
                "model_kwargs": {},
                "stream": False,
            }
        )

        model = component.build_model()

        mock_instance.bind.assert_called_once_with(response_format={"type": "json_object"})
        assert model == mock_bound_instance

    @patch("requests.get")
    def test_fallback_behavior_integration(self, mock_get, component):
        """Test fallback behavior when API is unavailable."""
        import requests

        mock_get.side_effect = requests.RequestException("Network error")

        models = component.get_models()

        from lfx.base.models.empiriolabs_constants import MODEL_NAMES

        assert models == MODEL_NAMES
        assert "Error fetching models" in component.status

    def test_update_build_config_integration(self, component):
        """Test update_build_config integration."""
        build_config = {"model_name": {"value": "qwen3-7-plus", "options": []}}

        with patch.object(component, "get_models", return_value=["qwen3-7-plus", "deepseek-v4-pro"]):
            updated_config = component.update_build_config(build_config, "new-key", "api_key")

        assert "model_name" in updated_config
        model_config = updated_config["model_name"]
        assert "qwen3-7-plus" in model_config["options"]
        assert "deepseek-v4-pro" in model_config["options"]

    @pytest.mark.skipif(os.getenv("EMPIRIOLABS_API_KEY") is None, reason="EMPIRIOLABS_API_KEY not set")
    def test_real_api_integration(self, component):
        """Test with real API key if available."""
        component.set_attributes(
            {
                "api_key": os.getenv("EMPIRIOLABS_API_KEY"),
                "model_name": "qwen3-7-plus",
                "temperature": 0.1,
                "max_tokens": 50,
                "model_kwargs": {},
                "json_mode": False,
                "stream": False,
            }
        )

        model = component.build_model()
        assert model is not None

        models = component.get_models()
        assert isinstance(models, list)
        assert len(models) > 0
