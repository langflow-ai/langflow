"""Unit tests for MiniMax model component."""
from unittest.mock import MagicMock, patch

import pytest
from lfx.components.minimax.minimax import MINIMAX_MODELS, MiniMaxModelComponent
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template


def test_minimax_initialization():
    component = MiniMaxModelComponent()
    assert component.display_name == "MiniMax"
    assert component.description == "Generate text using MiniMax LLMs."
    assert component.icon == "MiniMax"
    assert component.name == "MiniMaxModel"


def test_minimax_default_models():
    assert "MiniMax-M2.7" in MINIMAX_MODELS
    assert "MiniMax-M2.7-highspeed" in MINIMAX_MODELS
    assert len(MINIMAX_MODELS) == 2


def test_minimax_template():
    component = MiniMaxModelComponent()
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


@pytest.fixture
def mock_chat_openai(mocker):
    return mocker.patch("lfx.components.minimax.minimax.ChatOpenAI")


@pytest.mark.parametrize(
    ("temperature", "max_tokens"),
    [
        (0.5, 100),
        (1.0, 500),
        (0.7, 1000),
    ],
)
def test_minimax_build_model(mock_chat_openai, temperature, max_tokens):
    component = MiniMaxModelComponent()
    component.temperature = temperature
    component.max_tokens = max_tokens
    component.api_key = "test-key"
    component.model_name = "MiniMax-M2.7"
    component.model_kwargs = {}
    component.base_url = "https://api.minimax.io/v1"
    component.seed = 1
    component.json_mode = False

    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance

    model = component.build_model()

    mock_chat_openai.assert_called_once_with(
        max_tokens=max_tokens,
        model_kwargs={},
        model="MiniMax-M2.7",
        base_url="https://api.minimax.io/v1",
        api_key="test-key",
        temperature=temperature,
        seed=1,
    )
    assert model == mock_instance


def test_minimax_build_model_highspeed(mocker):
    component = MiniMaxModelComponent()
    component.temperature = 1.0
    component.max_tokens = 0
    component.api_key = "test-key"
    component.model_name = "MiniMax-M2.7-highspeed"
    component.model_kwargs = {}
    component.base_url = "https://api.minimax.io/v1"
    component.seed = 42
    component.json_mode = False

    mock_chat_openai = mocker.patch("lfx.components.minimax.minimax.ChatOpenAI", return_value=MagicMock())
    component.build_model()
    mock_chat_openai.assert_called_once_with(
        max_tokens=None,
        model_kwargs={},
        model="MiniMax-M2.7-highspeed",
        base_url="https://api.minimax.io/v1",
        api_key="test-key",
        temperature=1.0,
        seed=42,
    )


def test_minimax_temperature_zero_becomes_one(mocker):
    """MiniMax requires temperature in (0.0, 1.0], so 0 should become 1.0."""
    component = MiniMaxModelComponent()
    component.temperature = 0
    component.max_tokens = 100
    component.api_key = "test-key"
    component.model_name = "MiniMax-M2.7"
    component.model_kwargs = {}
    component.base_url = "https://api.minimax.io/v1"
    component.seed = 1
    component.json_mode = False

    mock_chat_openai = mocker.patch("lfx.components.minimax.minimax.ChatOpenAI", return_value=MagicMock())
    component.build_model()
    call_kwargs = mock_chat_openai.call_args[1]
    assert call_kwargs["temperature"] == 1.0


def test_minimax_temperature_none_becomes_one(mocker):
    """MiniMax requires temperature in (0.0, 1.0], so None should become 1.0."""
    component = MiniMaxModelComponent()
    component.temperature = None
    component.max_tokens = 100
    component.api_key = "test-key"
    component.model_name = "MiniMax-M2.7"
    component.model_kwargs = {}
    component.base_url = "https://api.minimax.io/v1"
    component.seed = 1
    component.json_mode = False

    mock_chat_openai = mocker.patch("lfx.components.minimax.minimax.ChatOpenAI", return_value=MagicMock())
    component.build_model()
    call_kwargs = mock_chat_openai.call_args[1]
    assert call_kwargs["temperature"] == 1.0


def test_minimax_default_base_url_when_empty(mocker):
    """When base_url is empty, should default to https://api.minimax.io/v1."""
    component = MiniMaxModelComponent()
    component.temperature = 1.0
    component.max_tokens = 100
    component.api_key = "test-key"
    component.model_name = "MiniMax-M2.7"
    component.model_kwargs = {}
    component.base_url = ""
    component.seed = 1
    component.json_mode = False

    mock_chat_openai = mocker.patch("lfx.components.minimax.minimax.ChatOpenAI", return_value=MagicMock())
    component.build_model()
    call_kwargs = mock_chat_openai.call_args[1]
    assert call_kwargs["base_url"] == "https://api.minimax.io/v1"


def test_minimax_json_mode(mocker):
    component = MiniMaxModelComponent()
    component.api_key = "test-key"
    component.json_mode = True
    component.temperature = 0.7
    component.max_tokens = 100
    component.model_name = "MiniMax-M2.7"
    component.model_kwargs = {}
    component.base_url = "https://api.minimax.io/v1"
    component.seed = 1

    mock_instance = MagicMock()
    mock_bound_instance = MagicMock()
    mock_instance.bind.return_value = mock_bound_instance
    mocker.patch("lfx.components.minimax.minimax.ChatOpenAI", return_value=mock_instance)

    model = component.build_model()
    mock_instance.bind.assert_called_once_with(response_format={"type": "json_object"})
    assert model == mock_bound_instance


def test_minimax_get_models_no_api_key():
    component = MiniMaxModelComponent()
    component.api_key = None
    models = component.get_models()
    assert models == MINIMAX_MODELS


def test_minimax_get_models(mocker):
    component = MiniMaxModelComponent()
    mock_get = mocker.patch("requests.get")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"id": "MiniMax-M2.7"},
            {"id": "MiniMax-M2.7-highspeed"},
        ]
    }
    mock_get.return_value = mock_response

    component.api_key = "test-key"
    component.base_url = "https://api.minimax.io/v1"
    models = component.get_models()
    assert models == ["MiniMax-M2.7", "MiniMax-M2.7-highspeed"]
    mock_get.assert_called_once_with(
        "https://api.minimax.io/v1/models",
        headers={"Authorization": "Bearer test-key", "Accept": "application/json"},
        timeout=10,
    )


def test_minimax_get_models_request_error(mocker):
    import requests as req

    component = MiniMaxModelComponent()
    component.api_key = "test-key"
    component.base_url = "https://api.minimax.io/v1"

    mocker.patch("requests.get", side_effect=req.RequestException("Connection error"))
    models = component.get_models()
    assert models == MINIMAX_MODELS


def test_minimax_update_build_config():
    component = MiniMaxModelComponent()
    build_config = {"model_name": {"options": []}}

    updated = component.update_build_config(build_config, "test-key", "api_key")
    assert "model_name" in updated

    updated = component.update_build_config(build_config, "MiniMax-M2.7", "model_name")
    assert "model_name" in updated


def test_minimax_error_handling(mock_chat_openai):
    component = MiniMaxModelComponent()
    component.api_key = "invalid-key"
    component.model_name = "MiniMax-M2.7"
    component.temperature = 1.0
    component.max_tokens = 100
    component.model_kwargs = {}
    component.base_url = "https://api.minimax.io/v1"
    component.seed = 1
    component.json_mode = False

    mock_chat_openai.side_effect = Exception("Invalid API key")

    with pytest.raises(Exception, match="Invalid API key"):
        component.build_model()
