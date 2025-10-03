import re
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from langchain_ollama import ChatOllama
from lfx.components.ollama.ollama import ChatOllamaComponent

from tests.base import ComponentTestBaseWithoutClient


class TestChatOllamaComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return ChatOllamaComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "base_url": "http://localhost:11434",
            "model_name": "ollama-model",
            "temperature": 0.1,
            "format": "json",
            "metadata": {},
            "tags": "",
            "mirostat": "Disabled",
            "mirostat_eta": None,
            "mirostat_tau": None,
            "num_ctx": 2048,
            "num_gpu": 1,
            "num_thread": 4,
            "repeat_last_n": 64,
            "repeat_penalty": 1.1,
            "tfs_z": 1.0,
            "timeout": 30,
            "top_k": 40,
            "top_p": 0.9,
            "verbose": False,
            "stop_tokens": "",
            "system": "",
            "tool_model_enabled": True,
            "template": "",
        }

    @pytest.fixture
    def file_names_mapping(self):
        # Provide an empty list or the actual mapping if versioned files exist
        return []

    @patch("lfx.components.ollama.ollama.ChatOllama")
    async def test_build_model(self, mock_chat_ollama, component_class, default_kwargs):
        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance
        component = component_class(**default_kwargs)
        model = component.build_model()
        mock_chat_ollama.assert_called_once_with(
            base_url="http://localhost:11434",
            model="ollama-model",
            mirostat=0,
            format="json",
            metadata={"keywords": ["model", "llm", "language model", "large language model"]},
            num_ctx=2048,
            num_gpu=1,
            num_thread=4,
            repeat_last_n=64,
            repeat_penalty=1.1,
            temperature=0.1,
            system="",
            tfs_z=1.0,
            timeout=30,
            top_k=40,
            top_p=0.9,
            verbose=False,
            template="",
        )
        assert model == mock_instance

    @patch("lfx.components.ollama.ollama.ChatOllama")
    async def test_build_model_missing_base_url(self, mock_chat_ollama, component_class, default_kwargs):
        # Make the mock raise an exception to simulate connection failure
        mock_chat_ollama.side_effect = Exception("connection error")
        component = component_class(**default_kwargs)
        component.base_url = None
        with pytest.raises(ValueError, match=re.escape("Unable to connect to the Ollama API.")):
            component.build_model()

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.get")
    async def test_get_models_success(self, mock_get, mock_post):
        component = ChatOllamaComponent()
        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "model1"},
                {component.JSON_NAME_KEY: "model2"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.side_effect = [
            {component.JSON_CAPABILITIES_KEY: [component.DESIRED_CAPABILITY]},
            {component.JSON_CAPABILITIES_KEY: []},
        ]
        mock_post.return_value = mock_post_response

        base_url = "http://localhost:11434"
        result = await component.get_models(base_url)
        assert result == ["model1"]
        assert mock_get.call_count == 1
        assert mock_post.call_count == 2

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.get")
    async def test_get_models_failure(self, mock_get):
        import httpx

        component = ChatOllamaComponent()
        mock_get.side_effect = httpx.RequestError("Connection error", request=None)
        base_url = "http://localhost:11434"
        with pytest.raises(ValueError, match=re.escape("Could not get model names from Ollama.")):
            await component.get_models(base_url)

    @pytest.mark.asyncio
    async def test_update_build_config_mirostat_disabled(self):
        component = ChatOllamaComponent()
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

    @pytest.mark.asyncio
    async def test_update_build_config_mirostat_enabled(self):
        component = ChatOllamaComponent()
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

    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.get")
    @pytest.mark.asyncio
    async def test_update_build_config_model_name(self, mock_get):
        component = ChatOllamaComponent()
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "model1"}, {"name": "model2"}]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        build_config = {
            "base_url": {"load_from_db": False, "value": None},
            "model_name": {"options": []},
            "tool_model_enabled": {"value": False},
        }
        field_value = None
        field_name = "model_name"
        component.base_url = None
        with pytest.raises(
            ValueError,
            match=re.escape("Ollama is not running on the provided base URL. Please start Ollama and try again."),
        ):
            await component.update_build_config(build_config, field_value, field_name)

    @pytest.mark.asyncio
    async def test_update_build_config_keep_alive(self):
        component = ChatOllamaComponent()
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
        "langchain_ollama.ChatOllama",
        return_value=ChatOllama(base_url="http://localhost:11434", model="llama3.1"),
    )
    def test_build_model_integration(self, _mock_chat_ollama):  # noqa: PT019
        component = ChatOllamaComponent()
        component.base_url = "http://localhost:11434"
        component.model_name = "llama3.1"
        component.mirostat = "Mirostat 2.0"
        component.mirostat_eta = 0.2
        component.mirostat_tau = 10.0
        component.temperature = 0.2
        component.verbose = True
        model = component.build_model()
        assert isinstance(model, ChatOllama)
        assert model.base_url == "http://localhost:11434"
        assert model.model == "llama3.1"

    @patch("socket.getaddrinfo")
    @patch("lfx.utils.util.Path")
    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_transforms_localhost_in_docker_container(
        self, mock_chat_ollama, mock_path_class, mock_getaddrinfo
    ):
        """Test that localhost URLs are transformed to host.docker.internal in Docker container."""

        # Mock Docker container detection
        def path_side_effect(path_str):
            mock_instance = MagicMock()
            if path_str == "/.dockerenv":
                mock_instance.exists.return_value = True
            else:
                mock_instance.exists.return_value = False
            return mock_instance

        mock_path_class.side_effect = path_side_effect

        # Mock getaddrinfo to succeed for host.docker.internal
        mock_getaddrinfo.return_value = [("AF_INET", "SOCK_STREAM", 6, "", ("192.168.65.2", 0))]

        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        component = ChatOllamaComponent()
        component.base_url = "http://localhost:11434"
        component.model_name = "llama3.1"
        component.mirostat = "Disabled"

        model = component.build_model()

        # Verify ChatOllama was called with host.docker.internal
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["base_url"] == "http://host.docker.internal:11434"
        assert model == mock_model

    @patch("lfx.utils.util.Path")
    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_no_transform_outside_container(self, mock_chat_ollama, mock_path_class):
        """Test that localhost URLs are NOT transformed when running outside a container."""
        # Mock no container environment
        mock_instance = MagicMock()
        mock_instance.exists.return_value = False
        mock_path_class.return_value = mock_instance

        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        component = ChatOllamaComponent()
        component.base_url = "http://localhost:11434"
        component.model_name = "llama3.1"
        component.mirostat = "Disabled"

        model = component.build_model()

        # Verify ChatOllama was called with original localhost URL
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["base_url"] == "http://localhost:11434"
        assert model == mock_model

    @patch("socket.getaddrinfo")
    @patch("lfx.utils.util.Path")
    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_transforms_localhost_in_podman_container(
        self, mock_chat_ollama, mock_path_class, mock_getaddrinfo
    ):
        """Test that localhost URLs are transformed to host.containers.internal in Podman container."""
        # Mock Podman container detection (no .dockerenv, but has podman in cgroup)
        cgroup_content = "12:pids:/podman/abc123\n"
        mock_cgroup = mock_open(read_data=cgroup_content)

        def path_side_effect(path_str):
            mock_instance = MagicMock()
            if path_str == "/.dockerenv":
                mock_instance.exists.return_value = False
            elif path_str == "/proc/self/cgroup":
                mock_instance.exists.return_value = True
                mock_instance.open = mock_cgroup
            else:
                mock_instance.exists.return_value = False
            return mock_instance

        mock_path_class.side_effect = path_side_effect

        # Mock getaddrinfo to succeed for host.containers.internal
        mock_getaddrinfo.return_value = [("AF_INET", "SOCK_STREAM", 6, "", ("192.168.65.2", 0))]

        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        component = ChatOllamaComponent()
        component.base_url = "http://localhost:11434"
        component.model_name = "llama3.1"
        component.mirostat = "Disabled"

        model = component.build_model()

        # Verify ChatOllama was called with host.containers.internal
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["base_url"] == "http://host.containers.internal:11434"
        assert model == mock_model

    @patch("socket.getaddrinfo")
    @patch("lfx.utils.util.Path")
    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_transforms_127_0_0_1_in_container(self, mock_chat_ollama, mock_path_class, mock_getaddrinfo):
        """Test that 127.0.0.1 URLs are also transformed in container."""

        # Mock Docker container detection
        def path_side_effect(path_str):
            mock_instance = MagicMock()
            if path_str == "/.dockerenv":
                mock_instance.exists.return_value = True
            else:
                mock_instance.exists.return_value = False
            return mock_instance

        mock_path_class.side_effect = path_side_effect

        # Mock getaddrinfo to succeed for host.docker.internal
        mock_getaddrinfo.return_value = [("AF_INET", "SOCK_STREAM", 6, "", ("192.168.65.2", 0))]

        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        component = ChatOllamaComponent()
        component.base_url = "http://127.0.0.1:11434"
        component.model_name = "llama3.1"
        component.mirostat = "Disabled"

        model = component.build_model()

        # Verify ChatOllama was called with host.docker.internal
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["base_url"] == "http://host.docker.internal:11434"
        assert model == mock_model
