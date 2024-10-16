from unittest.mock import MagicMock, patch
from urllib.parse import urljoin

import pytest
from langchain_community.chat_models.ollama import ChatOllama
from langflow.components.models.OllamaModel import ChatOllamaComponent


@pytest.fixture
def component():
    return ChatOllamaComponent()


@patch("httpx.Client.get")
def test_get_model_success(mock_get, component):
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "model1"}, {"name": "model2"}]}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    base_url = "http://localhost:11434"

    model_names = component.get_model(base_url)

    expected_url = urljoin(base_url, "/api/tags")

    mock_get.assert_called_once_with(expected_url)

    assert model_names == ["model1", "model2"]


@patch("httpx.Client.get")
def test_get_model_failure(mock_get, component):
    # Mock the response for the HTTP GET request to raise an exception
    mock_get.side_effect = Exception("HTTP request failed")

    url = "http://localhost:11434/api/tags"

    # Assert that the ValueError is raised when an exception occurs
    with pytest.raises(ValueError, match="Could not retrieve models"):
        component.get_model(url)


def test_update_build_config_mirostat_disabled(component):
    build_config = {
        "mirostat_eta": {"advanced": False, "value": 0.1},
        "mirostat_tau": {"advanced": False, "value": 5},
    }
    field_value = "Disabled"
    field_name = "mirostat"

    updated_config = component.update_build_config(build_config, field_value, field_name)

    assert updated_config["mirostat_eta"]["advanced"] is True
    assert updated_config["mirostat_tau"]["advanced"] is True
    assert updated_config["mirostat_eta"]["value"] is None
    assert updated_config["mirostat_tau"]["value"] is None


def test_update_build_config_mirostat_enabled(component):
    build_config = {
        "mirostat_eta": {"advanced": False, "value": None},
        "mirostat_tau": {"advanced": False, "value": None},
    }
    field_value = "Mirostat 2.0"
    field_name = "mirostat"

    updated_config = component.update_build_config(build_config, field_value, field_name)

    assert updated_config["mirostat_eta"]["advanced"] is False
    assert updated_config["mirostat_tau"]["advanced"] is False
    assert updated_config["mirostat_eta"]["value"] == 0.2
    assert updated_config["mirostat_tau"]["value"] == 10


@patch("httpx.Client.get")
def test_update_build_config_model_name(mock_get, component):
    # Mock the response for the HTTP GET request
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "model1"}, {"name": "model2"}]}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    build_config = {
        "base_url": {"load_from_db": False, "value": None},
        "model_name": {"options": []},
    }
    field_value = None
    field_name = "model_name"

    updated_config = component.update_build_config(build_config, field_value, field_name)

    assert updated_config["model_name"]["options"] == ["model1", "model2"]


def test_update_build_config_keep_alive(component):
    build_config = {"keep_alive": {"value": None, "advanced": False}}
    field_value = "Keep"
    field_name = "keep_alive_flag"

    updated_config = component.update_build_config(build_config, field_value, field_name)
    assert updated_config["keep_alive"]["value"] == "-1"
    assert updated_config["keep_alive"]["advanced"] is True

    field_value = "Immediately"
    updated_config = component.update_build_config(build_config, field_value, field_name)
    assert updated_config["keep_alive"]["value"] == "0"
    assert updated_config["keep_alive"]["advanced"] is True


@patch(
    "langchain_community.chat_models.ChatOllama",
    return_value=ChatOllama(base_url="http://localhost:11434", model="llama3.1"),
)
def test_build_model(_mock_chat_ollama, component):
    component.base_url = "http://localhost:11434"
    component.model_name = "llama3.1"
    component.mirostat = "Mirostat 2.0"
    component.mirostat_eta = 0.2  # Ensure this is set as a float
    component.mirostat_tau = 10.0  # Ensure this is set as a float
    component.temperature = 0.2
    component.verbose = True
    model = component.build_model()
    assert isinstance(model, ChatOllama)
    assert model.base_url == "http://localhost:11434"
    assert model.model == "llama3.1"
