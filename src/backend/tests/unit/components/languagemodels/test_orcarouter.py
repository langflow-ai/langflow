from unittest.mock import MagicMock

import pytest
from lfx.components.orcarouter.orcarouter import OrcaRouterComponent
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template


def test_orcarouter_initialization():
    component = OrcaRouterComponent()
    assert component.display_name == "OrcaRouter"
    assert component.icon == "OrcaRouter"
    assert "orcarouter/fusion" in component.description or "OrcaRouter" in component.description


def test_orcarouter_template():
    orcarouter = OrcaRouterComponent()
    component = Component(_code=orcarouter._code)
    frontend_node, _ = build_custom_component_template(component)

    assert isinstance(frontend_node, dict)
    assert "template" in frontend_node
    input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]

    expected_inputs = ["api_key", "model_name", "temperature", "max_tokens", "site_url", "app_name"]
    for input_name in expected_inputs:
        assert input_name in input_names


@pytest.fixture
def mock_chat_openai(mocker):
    return mocker.patch("lfx.components.orcarouter.orcarouter.ChatOpenAI")


@pytest.mark.parametrize(
    ("temperature", "max_tokens", "model_name"),
    [
        (0.5, 100, "orcarouter/fusion"),
        (1.0, 500, "openai/gpt-5.5"),
        (1.5, 1000, "anthropic/claude-opus-4.8"),
    ],
)
def test_orcarouter_build_model(mock_chat_openai, temperature, max_tokens, model_name):
    component = OrcaRouterComponent()
    component.api_key = "sk-orca-test-key"
    component.model_name = model_name
    component.temperature = temperature
    component.max_tokens = max_tokens
    component.site_url = ""
    component.app_name = ""

    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance

    model = component.build_model()

    mock_chat_openai.assert_called_once_with(
        model=model_name,
        openai_api_key="sk-orca-test-key",
        openai_api_base="https://api.orcarouter.ai/v1",
        temperature=temperature,
        max_tokens=max_tokens,
    )
    assert model == mock_instance


def test_orcarouter_fetch_models(mocker):
    component = OrcaRouterComponent()
    component.api_key = "sk-orca-test-key"

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"id": "orcarouter/fusion", "name": "Auto", "context_length": 128000},
            {"id": "openai/gpt-5.5", "name": "GPT-5.5", "context_length": 400000},
        ]
    }
    mock_get = mocker.patch("httpx.get", return_value=mock_response)

    models = component.fetch_models()

    assert {m["id"] for m in models} == {"orcarouter/fusion", "openai/gpt-5.5"}
    mock_get.assert_called_once_with(
        "https://api.orcarouter.ai/v1/models",
        headers={"Authorization": "Bearer sk-orca-test-key"},
        timeout=10.0,
    )


def test_orcarouter_missing_api_key():
    component = OrcaRouterComponent()
    component.api_key = ""
    component.model_name = "orcarouter/fusion"
    with pytest.raises(ValueError, match="API key is required"):
        component.build_model()
