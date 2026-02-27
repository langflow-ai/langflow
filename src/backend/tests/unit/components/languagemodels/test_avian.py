from unittest.mock import MagicMock

import pytest
from lfx.components.avian.avian import AVIAN_DEFAULT_MODELS, AvianModelComponent
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template


def test_avian_initialization():
    component = AvianModelComponent()
    assert component.display_name == "Avian"
    assert component.description == "Generate text using Avian LLMs."
    assert component.icon == "Bird"
    assert component.name == "AvianModel"


def test_avian_template():
    avian = AvianModelComponent()
    component = Component(_code=avian._code)
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
    return mocker.patch("langchain_openai.ChatOpenAI")


@pytest.mark.parametrize(
    ("temperature", "max_tokens"),
    [
        (0.5, 100),
        (1.0, 500),
        (1.5, 1000),
    ],
)
def test_avian_build_model(mock_chat_openai, temperature, max_tokens):
    component = AvianModelComponent()
    component.temperature = temperature
    component.max_tokens = max_tokens
    component.api_key = "test-key"
    component.model_name = "deepseek/deepseek-v3.2"
    component.model_kwargs = {}
    component.api_base = "https://api.avian.io/v1"
    component.seed = 1

    # Mock the ChatOpenAI instance
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance

    model = component.build_model()

    # Verify ChatOpenAI was called with correct params
    mock_chat_openai.assert_called_once_with(
        max_tokens=max_tokens,
        model_kwargs={},
        model="deepseek/deepseek-v3.2",
        base_url="https://api.avian.io/v1",
        api_key="test-key",
        temperature=temperature,
        seed=1,
        streaming=False,
    )
    assert model == mock_instance


def test_avian_build_model_json_mode(mock_chat_openai):
    component = AvianModelComponent()
    component.api_key = "test-key"
    component.json_mode = True
    component.temperature = 0.7
    component.max_tokens = 100
    component.model_name = "deepseek/deepseek-v3.2"
    component.model_kwargs = {}
    component.api_base = "https://api.avian.io/v1"
    component.seed = 1

    mock_instance = MagicMock()
    mock_bound_instance = MagicMock()
    mock_instance.bind.return_value = mock_bound_instance
    mock_chat_openai.return_value = mock_instance

    model = component.build_model()

    mock_instance.bind.assert_called_once_with(response_format={"type": "json_object"})
    assert model == mock_bound_instance


def test_avian_get_models(mocker):
    component = AvianModelComponent()

    # Mock requests.get
    mock_get = mocker.patch("requests.get")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"id": "deepseek/deepseek-v3.2"},
            {"id": "moonshotai/kimi-k2.5"},
        ]
    }
    mock_get.return_value = mock_response

    # Test with API key
    component.api_key = "test-key"
    component.api_base = "https://api.avian.io/v1"
    models = component.get_models()
    assert models == ["deepseek/deepseek-v3.2", "moonshotai/kimi-k2.5"]

    # Verify API call
    mock_get.assert_called_once_with(
        "https://api.avian.io/v1/models",
        headers={"Authorization": "Bearer test-key", "Accept": "application/json"},
        timeout=10,
    )


def test_avian_get_models_no_api_key():
    component = AvianModelComponent()
    component.api_key = None
    models = component.get_models()
    assert models == AVIAN_DEFAULT_MODELS


def test_avian_get_models_api_error(mocker):
    """Test that get_models falls back to defaults on API error."""
    component = AvianModelComponent()
    component.api_key = "test-key"
    component.api_base = "https://api.avian.io/v1"

    import requests

    mock_get = mocker.patch("requests.get", side_effect=requests.RequestException("Connection error"))
    models = component.get_models()

    assert models == AVIAN_DEFAULT_MODELS
    assert "Error fetching models" in component.status
    mock_get.assert_called_once()


def test_avian_get_models_malformed_response(mocker):
    """Test that get_models handles malformed API responses gracefully."""
    component = AvianModelComponent()
    component.api_key = "test-key"
    component.api_base = "https://api.avian.io/v1"

    # Test with non-dict response
    mock_get = mocker.patch("requests.get")
    mock_response = MagicMock()
    mock_response.json.return_value = "not a dict"
    mock_get.return_value = mock_response

    models = component.get_models()
    assert models == AVIAN_DEFAULT_MODELS

    # Test with malformed items in data list
    mock_response.json.return_value = {"data": [{"no_id": "missing"}, "not_a_dict", {"id": "valid/model"}]}
    models = component.get_models()
    assert models == ["valid/model"]


def test_avian_get_models_empty_data(mocker):
    """Test that get_models returns defaults when API returns empty data."""
    component = AvianModelComponent()
    component.api_key = "test-key"
    component.api_base = "https://api.avian.io/v1"

    mock_get = mocker.patch("requests.get")
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}
    mock_get.return_value = mock_response

    models = component.get_models()
    assert models == AVIAN_DEFAULT_MODELS


def test_avian_error_handling(mock_chat_openai):
    component = AvianModelComponent()
    component.api_key = "invalid-key"

    # Mock ChatOpenAI to raise exception
    mock_chat_openai.side_effect = Exception("Invalid API key")

    with pytest.raises(Exception, match="Invalid API key"):
        component.build_model()


def test_avian_get_exception_message():
    """Test _get_exception_message with various exception types."""
    component = AvianModelComponent()

    from openai import BadRequestError

    # Test with BadRequestError that has a dict body with message
    exc = BadRequestError(
        message="Bad request",
        response=MagicMock(),
        body={"message": "Invalid model specified"},
    )
    result = component._get_exception_message(exc)
    assert result == "Invalid model specified"

    # Test with BadRequestError that has a non-dict body (string)
    exc = BadRequestError(
        message="Bad request",
        response=MagicMock(),
        body="raw error text",
    )
    result = component._get_exception_message(exc)
    # Should fall through to super() since body is not a dict
    assert result is None or isinstance(result, str)

    # Test with BadRequestError that has None body
    exc = BadRequestError(
        message="Bad request",
        response=MagicMock(),
        body=None,
    )
    result = component._get_exception_message(exc)
    assert result is None or isinstance(result, str)

    # Test with a non-BadRequestError exception
    exc = ValueError("some error")
    result = component._get_exception_message(exc)
    assert result is None or isinstance(result, str)


def test_avian_update_build_config():
    component = AvianModelComponent()
    component.api_key = None
    build_config = {"model_name": {"options": []}}

    # Test that updating api_key triggers model refresh
    updated_config = component.update_build_config(build_config, "test-key", "api_key")
    assert "model_name" in updated_config
    assert updated_config["model_name"]["options"] == AVIAN_DEFAULT_MODELS

    # Test that updating model_name triggers refresh
    updated_config = component.update_build_config(build_config, "some-model", "model_name")
    assert "model_name" in updated_config

    # Test that updating unrelated field does NOT trigger refresh
    build_config_copy = {"model_name": {"options": ["original"]}}
    updated_config = component.update_build_config(build_config_copy, "value", "unrelated_field")
    assert updated_config["model_name"]["options"] == ["original"]
