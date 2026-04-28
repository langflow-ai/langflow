import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_openai import ChatOpenAI
from lfx.components.cometapi.cometapi import CometAPIComponent
from pydantic.v1 import SecretStr

from tests.base import ComponentTestBaseWithoutClient


class TestCometAPIComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return CometAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-cometapi-key",
            "model_name": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 1000,
            "seed": 1,
            "json_mode": False,
            "model_kwargs": {},
            "app_name": "test-app",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)

        assert component.display_name == "CometAPI"
        assert component.description == "All AI Models in One API 500+ AI Models"
        assert component.icon == "CometAPI"
        assert component.name == "CometAPIModel"
        assert component.api_key == "test-cometapi-key"
        assert component.model_name == "gpt-4o-mini"
        assert component.temperature == 0.7
        assert component.max_tokens == 1000
        assert component.seed == 1
        assert component.json_mode is False
        assert component.app_name == "test-app"

    @patch("lfx.components.cometapi.cometapi.ChatOpenAI")
    def test_build_model_success(self, mock_chat_openai, component_class, default_kwargs):
        """Test successful model building."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        component = component_class()
        component.set_attributes(default_kwargs)
        model = component.build_model()

        mock_chat_openai.assert_called_once_with(
            model="gpt-4o-mini",
            api_key="test-cometapi-key",
            max_tokens=1000,
            temperature=0.7,
            model_kwargs={},
            streaming=False,
            seed=1,
            base_url="https://api.cometapi.com/v1",
        )
        assert model == mock_instance

    @patch("lfx.components.cometapi.cometapi.ChatOpenAI")
    def test_build_model_with_json_mode(self, mock_chat_openai, component_class, default_kwargs):
        """Test model building with JSON mode enabled."""
        mock_instance = MagicMock()
        mock_bound_instance = MagicMock()
        mock_instance.bind.return_value = mock_bound_instance
        mock_chat_openai.return_value = mock_instance

        default_kwargs["json_mode"] = True
        component = component_class()
        component.set_attributes(default_kwargs)
        model = component.build_model()

        mock_chat_openai.assert_called_once()
        mock_instance.bind.assert_called_once_with(response_format={"type": "json_object"})
        assert model == mock_bound_instance

    @patch("lfx.components.cometapi.cometapi.ChatOpenAI")
    def test_build_model_with_streaming(self, mock_chat_openai, component_class, default_kwargs):
        """Test model building with streaming enabled."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        component = component_class()
        component.set_attributes(default_kwargs)
        component.stream = True
        component.build_model()

        _args, kwargs = mock_chat_openai.call_args
        assert kwargs["streaming"] is True

    def test_build_model_invalid_model_selection(self, component_class, default_kwargs):
        """Test that invalid model selection raises ValueError."""
        default_kwargs["model_name"] = "Select a model"
        component = component_class()
        component.set_attributes(default_kwargs)

        with pytest.raises(ValueError, match="Please select a valid CometAPI model"):
            component.build_model()

    @patch("lfx.components.cometapi.cometapi.ChatOpenAI")
    def test_build_model_exception_handling(self, mock_chat_openai, component_class, default_kwargs):
        """Test that build_model handles exceptions properly."""
        mock_chat_openai.side_effect = ValueError("Invalid API key")

        component = component_class()
        component.set_attributes(default_kwargs)

        with pytest.raises(ValueError, match="Could not connect to CometAPI"):
            component.build_model()

    @patch("requests.get")
    def test_get_models_success(self, mock_get, component_class, default_kwargs):
        """Test successful model fetching from API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"id": "gpt-4o-mini"}, {"id": "claude-3-5-haiku-latest"}, {"id": "gemini-2.5-flash"}]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        component = component_class()
        component.set_attributes(default_kwargs)
        models = component.get_models()

        assert models == ["gpt-4o-mini", "claude-3-5-haiku-latest", "gemini-2.5-flash"]
        mock_get.assert_called_once_with(
            "https://api.cometapi.com/v1/models",
            headers={"Content-Type": "application/json", "Authorization": "Bearer test-cometapi-key"},
            timeout=10,
        )

    @patch("requests.get")
    def test_get_models_json_decode_error(self, mock_get, component_class, default_kwargs):
        """Test model fetching with JSON decode error."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        component = component_class()
        component.set_attributes(default_kwargs)
        models = component.get_models()

        # Should return fallback models
        from lfx.base.models.cometapi_constants import MODEL_NAMES

        assert models == MODEL_NAMES
        assert "Error decoding models response" in component.status

    @pytest.mark.skipif(os.getenv("COMETAPI_KEY") is None, reason="COMETAPI_KEY is not set")
    def test_build_model_integration(self):
        """Integration test with real API key (if available)."""
        component = CometAPIComponent()
        component.api_key = SecretStr(os.getenv("COMETAPI_KEY"))
        component.model_name = "gpt-4o-mini"
        component.temperature = 0.2
        component.max_tokens = 100
        component.seed = 42

        model = component.build_model()
        assert isinstance(model, ChatOpenAI)
        assert model.model_name == "gpt-4o-mini"
        assert model.openai_api_base == "https://api.cometapi.com/v1"

    @pytest.mark.skipif(os.getenv("COMETAPI_KEY") is None, reason="COMETAPI_KEY is not set")
    def test_get_models_integration(self):
        """Integration test for get_models with real API key (if available)."""
        component = CometAPIComponent()
        component.api_key = SecretStr(os.getenv("COMETAPI_KEY"))

        models = component.get_models()
        assert isinstance(models, list)
        assert len(models) > 0
        # Should contain some expected models
        expected_models = ["gpt-4o-mini", "claude-3-5-haiku-latest", "gemini-2.5-flash"]
        assert any(model in models for model in expected_models)

    def test_component_inputs_structure(self, component_class):
        """Test that component has all required inputs."""
        component = component_class()
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

        for input_name in expected_inputs:
            assert input_name in input_names

    def test_component_input_requirements(self, component_class):
        """Test that required inputs are properly marked."""
        component = component_class()

        # Find required inputs
        required_inputs = [input_ for input_ in component.inputs if input_.required]
        required_names = [input_.name for input_ in required_inputs]

        assert "api_key" in required_names
        assert "model_name" in required_names

    def test_component_input_types(self, component_class):
        """Test that inputs have correct types."""
        component = component_class()

        # Find specific inputs by name
        api_key_input = next(input_ for input_ in component.inputs if input_.name == "api_key")
        model_name_input = next(input_ for input_ in component.inputs if input_.name == "model_name")
        temperature_input = next(input_ for input_ in component.inputs if input_.name == "temperature")

        assert api_key_input.field_type.value == "str"  # SecretStrInput
        assert model_name_input.field_type.value == "str"  # DropdownInput (actually returns "str")
        assert temperature_input.field_type.value == "slider"  # SliderInput
