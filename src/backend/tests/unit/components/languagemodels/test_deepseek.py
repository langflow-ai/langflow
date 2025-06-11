from unittest.mock import MagicMock

import pytest
from langflow.components.languagemodels import DeepSeekModelComponent
from langflow.custom.custom_component.component import Component
from langflow.custom.utils import build_custom_component_template


def test_deepseek_initialization():
    component = DeepSeekModelComponent()
    assert component.display_name == "DeepSeek"
    assert component.description == "Generate text using DeepSeek LLMs."
    assert component.icon == "DeepSeek"


def test_deepseek_template():
    deepseek = DeepSeekModelComponent()
    component = Component(_code=deepseek._code)
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
def test_deepseek_build_model(mock_chat_openai, temperature, max_tokens):
    component = DeepSeekModelComponent()
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
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key="test-key",
        temperature=temperature,
        seed=1,
        streaming=False,
    )
    assert model == mock_instance


def test_deepseek_get_models(mocker):
    component = DeepSeekModelComponent()

    # Mock requests.get
    mock_get = mocker.patch("requests.get")
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": "deepseek-chat"}, {"id": "deepseek-coder"}]}
    mock_get.return_value = mock_response

    # Test with API key
    component.api_key = "test-key"
    models = component.get_models()
    assert models == ["deepseek-chat", "deepseek-coder"]

    # Verify API call
    mock_get.assert_called_once_with(
        "https://api.deepseek.com/models",
        headers={"Authorization": "Bearer test-key", "Accept": "application/json"},
        timeout=10,
    )


def test_deepseek_error_handling(mock_chat_openai):
    component = DeepSeekModelComponent()
    component.api_key = "invalid-key"

    # Mock ChatOpenAI to raise exception
    mock_chat_openai.side_effect = Exception("Invalid API key")

    with pytest.raises(Exception, match="Invalid API key"):
        component.build_model()
