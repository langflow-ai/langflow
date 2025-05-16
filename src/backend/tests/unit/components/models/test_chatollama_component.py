from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_ollama import ChatOllama
from langflow.components.models import ChatOllamaComponent

from tests.base import ComponentTestBaseWithoutClient


class TestChatOllamaComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component_class class to test."""
        return ChatOllamaComponent()

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component_class."""
        return {
            "base_url": "http://localhost:11434",
            "model_name": "llama2",
            "temperature": 0.1,
            "format": None,
            "metadata": None,
            "mirostat": "Disabled",
            "mirostat_eta": None,
            "mirostat_tau": None,
            "num_ctx": None,
            "num_gpu": None,
            "num_thread": None,
            "repeat_last_n": None,
            "repeat_penalty": None,
            "stop_tokens": None,
            "system": None,
            "tfs_z": None,
            "timeout": None,
            "top_k": None,
            "top_p": None,
            "verbose": False,
            "template": None,
            "tool_model_enabled": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component_class doesn't have version-specific files."""
        return []

    @pytest.mark.asyncio
    @patch("langflow.components.models.ollama.httpx.AsyncClient.post")
    @patch("langflow.components.models.ollama.httpx.AsyncClient.get")
    async def test_get_models_success(self, mock_get, mock_post, component_class):
        # The revised approach to get_models filters based on model capabilities.
        # It requires one request to ollama to get the models and another to check
        # the capabilities of each model.
        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component_class.JSON_MODELS_KEY: [
                {component_class.JSON_NAME_KEY: "model1"},
                {component_class.JSON_NAME_KEY: "model2"},
            ]
        }
        mock_get.return_value = mock_get_response

        # Mock the response for the HTTP POST request to check capabilities.
        # Note that this is not exactly what happens if the Ollama server is running,
        # but it is a good approximation.
        # The first call checks the capabilities of model1, and the second call checks the capabilities of model2.
        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.side_effect = [
            {
                component_class.JSON_CAPABILITIES_KEY: [
                    component_class.DESIRED_CAPABILITY,
                    component_class.TOOL_CALLING_CAPABILITY,
                ]
            },
            {component_class.JSON_CAPABILITIES_KEY: [component_class.DESIRED_CAPABILITY]},
        ]
        mock_post.return_value = mock_post_response

        base_url_value = "http://localhost:11434"
        # Test with tool_model_enabled=True
        component_class.tool_model_enabled = True
        result = await component_class.get_models(base_url_value)
        assert result == ["model1"]  # Only model1 has tool calling capability
        assert mock_get.call_count == 1
        assert mock_post.call_count == 2

        # Reset mocks for next test
        mock_get.reset_mock()
        mock_post.reset_mock()
        mock_get.return_value = mock_get_response

        # Create new mock response for the second test
        mock_post_response2 = AsyncMock()
        mock_post_response2.raise_for_status.return_value = None
        mock_post_response2.json.side_effect = [
            {component_class.JSON_CAPABILITIES_KEY: [component_class.DESIRED_CAPABILITY]},  # model1 has only completion
            {component_class.JSON_CAPABILITIES_KEY: [component_class.DESIRED_CAPABILITY]},  # model2 has only completion
        ]
        mock_post.return_value = mock_post_response2

        # Test with tool_model_enabled=False
        component_class.tool_model_enabled = False
        result = await component_class.get_models(base_url_value)
        assert result == ["model1", "model2"]  # Both models have completion capability
        assert mock_get.call_count == 1
        assert mock_post.call_count == 2

    @pytest.mark.asyncio
    @patch("langflow.components.models.ollama.httpx.AsyncClient.get")
    async def test_get_models_failure(self, mock_get, component_class):
        # Simulate a network error for /api/tags
        import httpx

        mock_get.side_effect = httpx.RequestError("Connection error", request=None)

        base_url_value = "http://localhost:11434"
        with pytest.raises(ValueError, match="Could not get model names from Ollama."):
            await component_class.get_models(base_url_value, tool_model_enabled=False)

    async def test_update_build_config_mirostat_disabled(self, component_class):
        build_config = {
            "mirostat_eta": {"advanced": False, "value": 0.1},
            "mirostat_tau": {"advanced": False, "value": 5},
        }
        field_value = "Disabled"
        field_name = "mirostat"

        updated_config = await component_class.update_build_config(build_config, field_value, field_name)

        assert updated_config["mirostat_eta"]["advanced"] is True
        assert updated_config["mirostat_tau"]["advanced"] is True
        assert updated_config["mirostat_eta"]["value"] is None
        assert updated_config["mirostat_tau"]["value"] is None

    async def test_update_build_config_mirostat_enabled(self, component_class):
        build_config = {
            "mirostat_eta": {"advanced": False, "value": None},
            "mirostat_tau": {"advanced": False, "value": None},
        }
        field_value = "Mirostat 2.0"
        field_name = "mirostat"

        updated_config = await component_class.update_build_config(build_config, field_value, field_name)

        assert updated_config["mirostat_eta"]["advanced"] is False
        assert updated_config["mirostat_tau"]["advanced"] is False
        assert updated_config["mirostat_eta"]["value"] == 0.2
        assert updated_config["mirostat_tau"]["value"] == 10

    @patch("httpx.AsyncClient.get")
    async def test_update_build_config_model_name(self, mock_get, component_class):
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
            await component_class.update_build_config(build_config, field_value, field_name)

    async def test_update_build_config_keep_alive(self, component_class):
        build_config = {"keep_alive": {"value": None, "advanced": False}}
        field_value = "Keep"
        field_name = "keep_alive_flag"

        updated_config = await component_class.update_build_config(build_config, field_value, field_name)
        assert updated_config["keep_alive"]["value"] == "-1"
        assert updated_config["keep_alive"]["advanced"] is True

        field_value = "Immediately"
        updated_config = await component_class.update_build_config(build_config, field_value, field_name)
        assert updated_config["keep_alive"]["value"] == "0"
        assert updated_config["keep_alive"]["advanced"] is True

    @patch(
        "langchain_community.chat_models.ChatOllama",
        return_value=ChatOllama(base_url="http://localhost:11434", model="llama3.1"),
    )
    def test_build_model(self, _mock_chat_ollama, component_class):  # noqa: PT019
        component_class.base_url = "http://localhost:11434"
        component_class.model_name = "llama3.1"
        component_class.mirostat = "Mirostat 2.0"
        component_class.mirostat_eta = 0.2  # Ensure this is set as a float
        component_class.mirostat_tau = 10.0  # Ensure this is set as a float
        component_class.temperature = 0.2
        component_class.verbose = True
        model = component_class.build_model()
        assert isinstance(model, ChatOllama)
        assert model.base_url == "http://localhost:11434"
        assert model.model == "llama3.1"
