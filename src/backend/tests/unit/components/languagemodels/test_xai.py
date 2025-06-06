from unittest.mock import MagicMock, patch

import pytest
from langflow.components.languagemodels import XAIModelComponent
from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template
from langflow.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
    SliderInput,
)

from tests.base import ComponentTestBaseWithoutClient


class TestXAIComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return XAIModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "temperature": 0.1,
            "max_tokens": 50,
            "api_key": "dummy-key",
            "model_name": "grok-2-latest",
            "model_kwargs": {},
            "base_url": "https://api.x.ai/v1",
            "seed": 42,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_initialization(self, component_class):
        component = component_class()
        assert component.display_name == "xAI"
        assert component.description == "Generates text using xAI models like Grok."
        assert component.icon == "xAI"
        assert component.name == "xAIModel"

    def test_template(self, default_kwargs):
        component = XAIModelComponent(**default_kwargs)
        comp = Component(_code=component._code)
        frontend_node, _ = build_custom_component_template(comp)
        assert isinstance(frontend_node, dict)
        assert "template" in frontend_node
        input_names = [inp["name"] for inp in frontend_node["template"].values() if isinstance(inp, dict)]
        expected_inputs = [
            "max_tokens",
            "model_kwargs",
            "json_mode",
            "model_name",
            "base_url",
            "api_key",
            "temperature",
            "seed",
        ]
        for input_name in expected_inputs:
            assert input_name in input_names

    def test_inputs(self):
        component = XAIModelComponent()
        inputs = component.inputs
        expected_inputs = {
            "max_tokens": IntInput,
            "model_kwargs": DictInput,
            "json_mode": BoolInput,
            "model_name": DropdownInput,
            "base_url": MessageTextInput,
            "api_key": SecretStrInput,
            "temperature": SliderInput,
            "seed": IntInput,
        }
        for name, input_type in expected_inputs.items():
            matching_inputs = [inp for inp in inputs if isinstance(inp, input_type) and inp.name == name]
            assert matching_inputs, f"Missing or incorrect input: {name}"
            if name == "model_name":
                input_field = matching_inputs[0]
                assert input_field.value == "grok-2-latest"
                assert input_field.refresh_button is True
            elif name == "temperature":
                input_field = matching_inputs[0]
                assert input_field.value == 0.1
                assert input_field.range_spec.min == 0
                assert input_field.range_spec.max == 2

    def test_build_model(self, component_class, default_kwargs, mocker):
        component = component_class(**default_kwargs)
        component.temperature = 0.7
        component.max_tokens = 100
        component.api_key = "test-key"
        component.model_name = "grok-2-latest"
        component.model_kwargs = {}
        component.base_url = "https://api.x.ai/v1"
        component.seed = 1

        mock_chat_openai = mocker.patch("langflow.components.languagemodels.xai.ChatOpenAI", return_value=MagicMock())
        model = component.build_model()
        mock_chat_openai.assert_called_once_with(
            max_tokens=100,
            model_kwargs={},
            model="grok-2-latest",
            base_url="https://api.x.ai/v1",
            api_key="test-key",
            temperature=0.7,
            seed=1,
        )
        assert model == mock_chat_openai.return_value

    def test_get_models(self):
        component = XAIModelComponent()
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "models": [
                    {"id": "grok-2-latest", "aliases": ["grok-2"]},
                    {"id": "grok-1", "aliases": []},
                ]
            }
            mock_get.return_value = mock_response

            component.api_key = "test-key"
            models = component.get_models()
            assert sorted(models) == ["grok-1", "grok-2", "grok-2-latest"]
            mock_get.assert_called_once_with(
                "https://api.x.ai/v1/language-models",
                headers={
                    "Authorization": "Bearer test-key",
                    "Accept": "application/json",
                },
                timeout=10,
            )

    def test_get_models_no_api_key(self):
        component = XAIModelComponent(api_key=None)
        models = component.get_models()
        assert models == ["grok-2-latest"]

    def test_build_model_error(self, component_class, mocker):
        from openai import BadRequestError

        component = component_class()
        component.api_key = "invalid-key"
        component.model_name = "grok-2-latest"
        component.temperature = 0.7
        component.max_tokens = 100
        component.model_kwargs = {}
        component.base_url = "https://api.x.ai/v1"
        component.seed = 1

        mocker.patch(
            "langflow.components.languagemodels.xai.ChatOpenAI",
            side_effect=BadRequestError(
                message="Invalid API key",
                response=MagicMock(),
                body={"message": "Invalid API key provided"},
            ),
        )
        with pytest.raises(BadRequestError) as exc_info:
            component.build_model()
        assert exc_info.value.body["message"] == "Invalid API key provided"

    def test_json_mode(self, component_class, mocker):
        component = component_class()
        component.api_key = "test-key"
        component.json_mode = True
        component.temperature = 0.7
        component.max_tokens = 100
        component.model_name = "grok-2-latest"
        component.model_kwargs = {}
        component.base_url = "https://api.x.ai/v1"
        component.seed = 1

        mock_instance = MagicMock()
        mock_bound_instance = MagicMock()
        mock_instance.bind.return_value = mock_bound_instance
        mocker.patch("langflow.components.languagemodels.xai.ChatOpenAI", return_value=mock_instance)

        model = component.build_model()
        mock_instance.bind.assert_called_once_with(response_format={"type": "json_object"})
        assert model == mock_bound_instance

    def test_update_build_config(self):
        component = XAIModelComponent()
        build_config = {"model_name": {"options": []}}

        updated_config = component.update_build_config(build_config, "test-key", "api_key")
        assert "model_name" in updated_config

        updated_config = component.update_build_config(build_config, "grok-2-latest", "model_name")
        assert "model_name" in updated_config
