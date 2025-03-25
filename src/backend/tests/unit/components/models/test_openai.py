from unittest.mock import MagicMock

import pytest
from langflow.components.models import OpenAIModelComponent
from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template


def test_openai_initialization():
    component = OpenAIModelComponent()
    assert component.display_name == "OpenAI"
    assert component.description == "Generates text using OpenAI LLMs."
    assert component.icon == "OpenAI"


def test_openai_template():
    openai = OpenAIModelComponent()
    component = Component(_code=openai._code)
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
        "openai_api_base",
        "api_key",
        "temperature",
        "seed",
    ]

    for input_name in expected_inputs:
        assert input_name in input_names


@pytest.fixture
def mock_chat_openai(mocker):
    return mocker.patch("langflow.components.models.openai_chat_model.ChatOpenAI")


@pytest.mark.parametrize(
    ("temperature", "max_tokens"),
    [
        (0.5, 100),
        (1.0, 500),
        (1.5, 1000),
    ],
)
def test_openai_build_model(mock_chat_openai, temperature, max_tokens):
    component = OpenAIModelComponent()
    component.temperature = temperature
    component.max_tokens = max_tokens
    component.api_key = "test-key"

    # Mock the ChatOpenAI instance
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance

    model = component.build_model()

    # Verify ChatOpenAI was called with correct params
    mock_chat_openai.assert_called_once_with(
        max_tokens=max_tokens,
        model_kwargs={},
        model="gpt-4o",
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        temperature=temperature,
        seed=1,
        max_retries=5,
        request_timeout=700,
    )
    assert model == mock_instance


def test_openai_get_models(mocker):
    component = OpenAIModelComponent()

    # Mock requests.get
    mock_get = mocker.patch("requests.get")
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4o"}]}
    mock_get.return_value = mock_response

    # Test with API key
    component.api_key = "test-key"
    models = component.get_models()
    assert models == ["gpt-4o-mini", "gpt-4o"]

    # Verify API call
    mock_get.assert_called_once_with(
        "https://api.openai.com/v1/models",
        headers={"Authorization": "Bearer test-key", "Accept": "application/json"},
        timeout=10,
    )


def test_openai_error_handling(mock_chat_openai):
    component = OpenAIModelComponent()
    component.api_key = "invalid-key"

    # Mock ChatOpenAI to raise exception
    mock_chat_openai.side_effect = Exception("Invalid API key")

    with pytest.raises(Exception, match="Invalid API key"):
        component.build_model()
