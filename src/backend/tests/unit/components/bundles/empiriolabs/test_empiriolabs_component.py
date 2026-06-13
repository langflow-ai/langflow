import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_openai import ChatOpenAI
from lfx.components.empiriolabs.empiriolabs import EmpirioLabsModelComponent
from pydantic.v1 import SecretStr

from tests.base import ComponentTestBaseWithoutClient


class TestEmpirioLabsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return EmpirioLabsModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-empiriolabs-key",
            "model_name": "qwen3-7-plus",
            "temperature": 0.1,
            "max_tokens": 1000,
            "seed": 1,
            "json_mode": False,
            "model_kwargs": {},
            "stream": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)

        assert component.display_name == "EmpirioLabs"
        assert component.description == "Generates text using EmpirioLabs AI LLMs (OpenAI compatible)."
        assert component.icon == "EmpirioLabs"
        assert component.name == "EmpirioLabsModel"
        assert component.api_key == "test-empiriolabs-key"
        assert component.model_name == "qwen3-7-plus"
        assert component.temperature == 0.1
        assert component.max_tokens == 1000
        assert component.seed == 1
        assert component.json_mode is False

    @patch("lfx.components.empiriolabs.empiriolabs.ChatOpenAI")
    def test_build_model_success(self, mock_chat_openai, component_class, default_kwargs):
        """Test successful model building."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        component = component_class()
        component.set_attributes(default_kwargs)
        model = component.build_model()

        mock_chat_openai.assert_called_once_with(
            model="qwen3-7-plus",
            api_key="test-empiriolabs-key",
            max_tokens=1000,
            temperature=0.1,
            model_kwargs={},
            streaming=False,
            seed=1,
            base_url="https://api.empiriolabs.ai/v1",
        )
        assert model == mock_instance

    @patch("lfx.components.empiriolabs.empiriolabs.ChatOpenAI")
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

    @patch("lfx.components.empiriolabs.empiriolabs.ChatOpenAI")
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

    @patch("lfx.components.empiriolabs.empiriolabs.ChatOpenAI")
    def test_build_model_exception_handling(self, mock_chat_openai, component_class, default_kwargs):
        """Test that build_model handles exceptions properly."""
        mock_chat_openai.side_effect = ValueError("Invalid API key")

        component = component_class()
        component.set_attributes(default_kwargs)

        with pytest.raises(ValueError, match="Could not connect to EmpirioLabs API"):
            component.build_model()

    @patch("requests.get")
    def test_get_models_success(self, mock_get, component_class, default_kwargs):
        """Test successful model fetching from API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"id": "qwen3-7-plus"}, {"id": "deepseek-v4-pro"}, {"id": "glm-5-1"}]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        component = component_class()
        component.set_attributes(default_kwargs)
        models = component.get_models()

        assert models == ["qwen3-7-plus", "deepseek-v4-pro", "glm-5-1"]
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_get_models_fallback(self, mock_get, component_class, default_kwargs):
        """Test model fetching falls back to constants on request error."""
        import requests

        mock_get.side_effect = requests.RequestException("Network error")

        component = component_class()
        component.set_attributes(default_kwargs)
        models = component.get_models()

        from lfx.base.models.empiriolabs_constants import MODEL_NAMES

        assert models == MODEL_NAMES
        assert "Error fetching models" in component.status

    @pytest.mark.skipif(os.getenv("EMPIRIOLABS_API_KEY") is None, reason="EMPIRIOLABS_API_KEY is not set")
    def test_build_model_integration(self):
        """Integration test with real API key (if available)."""
        component = EmpirioLabsModelComponent()
        component.api_key = SecretStr(os.getenv("EMPIRIOLABS_API_KEY")).get_secret_value()
        component.model_name = "qwen3-7-plus"
        component.temperature = 0.2
        component.max_tokens = 100
        component.seed = 42
        component.stream = False
        component.model_kwargs = {}
        component.json_mode = False

        model = component.build_model()
        assert isinstance(model, ChatOpenAI)
        assert model.model_name == "qwen3-7-plus"
        assert model.openai_api_base == "https://api.empiriolabs.ai/v1"

    def test_component_inputs_structure(self, component_class):
        """Test that component has all required inputs."""
        component = component_class()
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

        for input_name in expected_inputs:
            assert input_name in input_names

    def test_component_input_types(self, component_class):
        """Test that inputs have correct types."""
        component = component_class()

        api_key_input = next(input_ for input_ in component.inputs if input_.name == "api_key")
        model_name_input = next(input_ for input_ in component.inputs if input_.name == "model_name")
        temperature_input = next(input_ for input_ in component.inputs if input_.name == "temperature")

        assert api_key_input.field_type.value == "str"  # SecretStrInput
        assert model_name_input.field_type.value == "str"  # DropdownInput (returns "str")
        assert temperature_input.field_type.value == "slider"  # SliderInput
