from unittest.mock import MagicMock, patch

import pytest
from langflow.components.models import MacrocosmosComponent
from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template
from langflow.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
    SliderInput,
    StrInput,
)

from tests.base import ComponentTestBaseWithoutClient


class TestMacrocosmosComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return MacrocosmosComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "macrocosmos_url": "https://sn1.api.macrocosmos.ai/v1",
            "model_name": "hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4",
            "inference_mode": "Base-Inference",
            "macrocosmos_api_key": "dummy-key",
            "max_new_tokens": 4096,
            "top_k": 50,
            "top_p": 0.95,
            "temperature": 0.7,
            "do_sample": True,
            "output_parser": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_initialization(self, component_class):
        component = component_class()
        assert component.display_name == "Macrocosmos"
        assert component.description == "Generate text using Macrocosmos' Apex, powered by Bittensor."
        assert component.icon == "Macrocosmos"
        assert component.name == "MacrocosmosModel"

    def test_template(self, default_kwargs):
        component = MacrocosmosComponent(**default_kwargs)
        comp = Component(_code=component._code)
        frontend_node, _ = build_custom_component_template(comp)
        assert isinstance(frontend_node, dict)
        assert "template" in frontend_node
        input_names = [inp["name"] for inp in frontend_node["template"].values() if isinstance(inp, dict)]
        expected_inputs = [
            "macrocosmos_url",
            "model_name",
            "inference_mode",
            "macrocosmos_api_key",
            "max_new_tokens",
            "top_k",
            "top_p",
            "temperature",
            "do_sample",
            "output_parser",
        ]
        for input_name in expected_inputs:
            assert input_name in input_names

    def test_inputs(self):
        component = MacrocosmosComponent()
        inputs = component.inputs
        expected_inputs = {
            "macrocosmos_url": StrInput,
            "model_name": DropdownInput,
            "inference_mode": DropdownInput,
            "macrocosmos_api_key": SecretStrInput,
            "max_new_tokens": IntInput,
            "top_k": IntInput,
            "top_p": FloatInput,
            "temperature": FloatInput,
            "do_sample": BoolInput,
        }
        for name, input_type in expected_inputs.items():
            matching_inputs = [inp for inp in inputs if isinstance(inp, input_type) and inp.name == name]
            assert matching_inputs, f"Missing or incorrect input: {name}"
            if name == "model_name":
                input_field = matching_inputs[0]
                assert "hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4" in input_field.options
                assert input_field.value == "Default"
            elif name == "inference_mode":
                input_field = matching_inputs[0]
                assert "Base-Inference" in input_field.options
                assert input_field.value == "Base-Inference"
            elif name == "temperature":
                input_field = matching_inputs[0]
                assert input_field.value == 0.7

    def test_build_model(self, component_class, default_kwargs, mocker):
        component = component_class(**default_kwargs)
        component.temperature = 0.7
        component.max_new_tokens = 4096
        component.macrocosmos_api_key = "test-key"
        component.model_name = "hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4"
        component.macrocosmos_url = "https://sn1.api.macrocosmos.ai/v1"
        component.inference_mode = "Base-Inference"
        component.top_k = 50
        component.top_p = 0.95
        component.do_sample = True
        component.seed = 42

        sample_params = {
            "top_k": 50,
            "top_p": 0.95,
            "temperature": 0.7,
            "do_sample": True,
        }

        mock_chat_openai = mocker.patch("langflow.components.models.macrocosmos.ChatOpenAI", return_value=MagicMock())
        model = component.build_model()
        mock_chat_openai.assert_called_once_with(
            model="hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4",
            base_url="https://sn1.api.macrocosmos.ai/v1",
            api_key="test-key",
            inference_mode="Base-Inference",
            extra_body=sample_params,
            seed=42,
        )
        assert model == mock_chat_openai.return_value

    def test_build_model_error(self, component_class, mocker):
        from openai import BadRequestError

        component = component_class()
        component.macrocosmos_api_key = "invalid-key"
        component.model_name = "hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4"
        component.macrocosmos_url = "https://sn1.api.macrocosmos.ai/v1"
        component.inference_mode = "Base-Inference"
        component.temperature = 0.7
        component.top_k = 50
        component.top_p = 0.95
        component.do_sample = True
        component.seed = 42

        mocker.patch(
            "langflow.components.models.macrocosmos.ChatOpenAI",
            side_effect=BadRequestError(
                message="Invalid API key",
                response=MagicMock(),
                body={"message": "Invalid API key"},
            ),
        )
        with pytest.raises(BadRequestError) as exc_info:
            component.build_model()
        assert exc_info.value.body["message"] == "Invalid API key" 