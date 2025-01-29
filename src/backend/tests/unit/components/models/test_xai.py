from unittest.mock import MagicMock, patch

import pytest
from langflow.components.models import XAIModelComponent
from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template
from langflow.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    IntInput,
    SecretStrInput,
    SliderInput,
    StrInput,
)


def test_xai_initialization():
    component = XAIModelComponent()
    assert component.display_name == "xAI"
    assert component.description == "Generates text using xAI models like Grok."
    assert component.icon == "xAI"
    assert component.name == "xAIModel"


def test_xai_template():
    xai = XAIModelComponent()
    component = Component(_code=xai._code)
    frontend_node, _ = build_custom_component_template(component)

    # Verify basic structure
    assert isinstance(frontend_node, dict)

    # Verify inputs
    assert "template" in frontend_node
    input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]

    expected_inputs = [
        "max_tokens",
        "model_kwargs",
        "json_mode",
        "model_name",
        "api_base",
        "api_key",
        "temperature",
        "seed",
    ]

    for input_name in expected_inputs:
        assert input_name in input_names


@pytest.fixture
def mock_chat_openai(mocker):
    return mocker.patch("langflow.components.models.xai.ChatOpenAI")


def test_xai_inputs():
    component = XAIModelComponent()
    inputs = component.inputs

    # Define expected input types and their names
    expected_inputs = {
        "max_tokens": IntInput,
        "model_kwargs": DictInput,
        "json_mode": BoolInput,
        "model_name": DropdownInput,
        "api_base": StrInput,
        "api_key": SecretStrInput,
        "temperature": SliderInput,
        "seed": IntInput,
    }

    # Check if all expected inputs are present and have correct type
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


def test_xai_build_model(mock_chat_openai):
    component = XAIModelComponent()
    component.temperature = 0.7
    component.max_tokens = 100
    component.api_key = "test-key"
    component.model_name = "grok-2-latest"
    component.model_kwargs = {}
    component.api_base = "https://api.x.ai/v1"
    component.seed = 1

    # Mock the ChatOpenAI instance
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance

    model = component.build_model()

    # Verify ChatOpenAI was called with correct params
    mock_chat_openai.assert_called_once_with(
        max_tokens=100,
        model_kwargs={},
        model="grok-2-latest",
        base_url="https://api.x.ai/v1",
        api_key="test-key",
        temperature=0.7,
        seed=1,
    )
    assert model == mock_instance


def test_xai_get_models():
    component = XAIModelComponent()

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [{"id": "grok-2-latest", "aliases": ["grok-2"]}, {"id": "grok-1", "aliases": []}]
        }
        mock_get.return_value = mock_response

        # Test with API key
        component.api_key = "test-key"
        models = component.get_models()
        assert sorted(models) == ["grok-1", "grok-2", "grok-2-latest"]

        # Verify API call
        mock_get.assert_called_once_with(
            "https://api.x.ai/v1/language-models",
            headers={"Authorization": "Bearer test-key", "Accept": "application/json"},
            timeout=10,
        )


def test_xai_get_models_no_api_key():
    component = XAIModelComponent()
    component.api_key = None
    models = component.get_models()
    assert models == ["grok-2-latest"]


def test_xai_build_model_error(mock_chat_openai):
    from openai import BadRequestError

    component = XAIModelComponent()
    component.api_key = "invalid-key"
    component.model_name = "grok-2-latest"
    component.temperature = 0.7
    component.max_tokens = 100
    component.model_kwargs = {}
    component.api_base = "https://api.x.ai/v1"
    component.seed = 1

    # Create a mock BadRequestError
    mock_error = BadRequestError(
        message="Invalid API key", response=MagicMock(), body={"message": "Invalid API key provided"}
    )

    # Configure the mock to raise the error when called
    mock_chat_openai.side_effect = mock_error

    # Should raise the BadRequestError
    with pytest.raises(BadRequestError) as exc_info:
        component.build_model()

    # Verify the error message
    assert exc_info.value.body["message"] == "Invalid API key provided"


def test_xai_json_mode(mock_chat_openai):
    component = XAIModelComponent()
    component.api_key = "test-key"
    component.json_mode = True
    component.temperature = 0.7
    component.max_tokens = 100
    component.model_name = "grok-2-latest"
    component.model_kwargs = {}
    component.api_base = "https://api.x.ai/v1"
    component.seed = 1

    # Mock the ChatOpenAI instance and its bind method
    mock_instance = MagicMock()
    mock_bound_instance = MagicMock()
    mock_instance.bind.return_value = mock_bound_instance
    mock_chat_openai.return_value = mock_instance

    model = component.build_model()

    # Verify ChatOpenAI was called with correct params
    mock_chat_openai.assert_called_once_with(
        max_tokens=100,
        model_kwargs={},
        model="grok-2-latest",
        base_url="https://api.x.ai/v1",
        api_key="test-key",
        temperature=0.7,
        seed=1,
    )

    # Verify bind was called with json_object response format
    mock_instance.bind.assert_called_once_with(response_format={"type": "json_object"})
    assert model == mock_bound_instance


def test_xai_update_build_config():
    component = XAIModelComponent()
    build_config = {"model_name": {"options": []}}

    # Test with API key change
    updated_config = component.update_build_config(build_config, "test-key", "api_key")
    assert "model_name" in updated_config

    # Test with model name change
    updated_config = component.update_build_config(build_config, "grok-2-latest", "model_name")
    assert "model_name" in updated_config
