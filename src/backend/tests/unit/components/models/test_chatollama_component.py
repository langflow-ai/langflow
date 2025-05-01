from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_ollama import ChatOllama
from langflow.components.models import ChatOllamaComponent


@pytest.fixture
def component():
    return ChatOllamaComponent()


@pytest.mark.asyncio
@patch("langflow.components.models.ollama.httpx.AsyncClient.post")
@patch("langflow.components.models.ollama.httpx.AsyncClient.get")
async def test_get_models_success(mock_get, mock_post, component):
    # The revised approach to get_models filters based on model capabilities.
    # It requires one request to ollama to get the models and another to check
    # the capabilities of each model.
    mock_get_response = AsyncMock()
    mock_get_response.raise_for_status.return_value = None
    mock_get_response.json.return_value = {
        component.JSON_MODELS_KEY: [{component.JSON_NAME_KEY: "model1"}, {component.JSON_NAME_KEY: "model2"}]
    }
    mock_get.return_value = mock_get_response

    # Mock the response for the HTTP POST request to check capabilities.
    # Note that this is not exactly what happens if the Ollama server is running,
    # but it is a good approximation.
    # The first call checks the capabilities of model1, and the second call checks the capabilities of model2.
    mock_post_response = AsyncMock()
    mock_post_response.raise_for_status.return_value = None
    mock_post_response.json.side_effect = [
        {component.JSON_CAPABILITIES_KEY: [component.DESIRED_CAPABILITY]},
        {component.JSON_CAPABILITIES_KEY: []},
    ]
    mock_post.return_value = mock_post_response

    base_url = "http://localhost:11434"
    result = await component.get_models(base_url)

    # Check that the correct URL was used for the GET request
    assert result == ["model1"]
    assert mock_get.call_count == 1
    assert mock_post.call_count == 2


@pytest.mark.asyncio
@patch("langflow.components.models.ollama.httpx.AsyncClient.get")
async def test_get_models_failure(mock_get, component):
    # Simulate a network error for /api/tags
    import httpx

    mock_get.side_effect = httpx.RequestError("Connection error", request=None)

    base_url = "http://localhost:11434"
    with pytest.raises(ValueError, match="Could not get model names from Ollama."):
        await component.get_models(base_url)


async def test_update_build_config_mirostat_disabled(component):
    build_config = {
        "mirostat_eta": {"advanced": False, "value": 0.1},
        "mirostat_tau": {"advanced": False, "value": 5},
    }
    field_value = "Disabled"
    field_name = "mirostat"

    updated_config = await component.update_build_config(build_config, field_value, field_name)

    assert updated_config["mirostat_eta"]["advanced"] is True
    assert updated_config["mirostat_tau"]["advanced"] is True
    assert updated_config["mirostat_eta"]["value"] is None
    assert updated_config["mirostat_tau"]["value"] is None


async def test_update_build_config_mirostat_enabled(component):
    build_config = {
        "mirostat_eta": {"advanced": False, "value": None},
        "mirostat_tau": {"advanced": False, "value": None},
    }
    field_value = "Mirostat 2.0"
    field_name = "mirostat"

    updated_config = await component.update_build_config(build_config, field_value, field_name)

    assert updated_config["mirostat_eta"]["advanced"] is False
    assert updated_config["mirostat_tau"]["advanced"] is False
    assert updated_config["mirostat_eta"]["value"] == 0.2
    assert updated_config["mirostat_tau"]["value"] == 10


@patch("httpx.AsyncClient.get")
async def test_update_build_config_model_name(mock_get, component):
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

    with pytest.raises(ValueError, match="No valid Ollama URL found"):
        await component.update_build_config(build_config, field_value, field_name)


async def test_update_build_config_keep_alive(component):
    build_config = {"keep_alive": {"value": None, "advanced": False}}
    field_value = "Keep"
    field_name = "keep_alive_flag"

    updated_config = await component.update_build_config(build_config, field_value, field_name)
    assert updated_config["keep_alive"]["value"] == "-1"
    assert updated_config["keep_alive"]["advanced"] is True

    field_value = "Immediately"
    updated_config = await component.update_build_config(build_config, field_value, field_name)
    assert updated_config["keep_alive"]["value"] == "0"
    assert updated_config["keep_alive"]["advanced"] is True


@patch(
    "langchain_community.chat_models.ChatOllama",
    return_value=ChatOllama(base_url="http://localhost:11434", model="llama3.1"),
)
def test_build_model(_mock_chat_ollama, component):  # noqa: PT019
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
