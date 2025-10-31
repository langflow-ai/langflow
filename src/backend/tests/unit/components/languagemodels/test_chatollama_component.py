import re
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from langchain_ollama import ChatOllama
from lfx.base.models.ollama_constants import DEFAULT_OLLAMA_API_URL
from lfx.components.ollama.ollama import ChatOllamaComponent
from lfx.schema import Data, DataFrame

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
            # mirostat is not included when disabled (set to None and filtered out)
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

    @patch("lfx.components.ollama.ollama.ChatOllama")
    async def test_build_model_with_mirostat_enabled(self, mock_chat_ollama, component_class):
        """Test that mirostat parameters are included when Mirostat is enabled."""
        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance

        component = component_class(
            base_url="http://localhost:11434",
            model_name="ollama-model",
            mirostat="Mirostat",  # Setting to Mirostat (value 1)
            mirostat_eta=0.1,
            mirostat_tau=5.0,
            temperature=0.1,
        )
        model = component.build_model()

        # Verify that mirostat and its related params ARE passed
        call_kwargs = mock_chat_ollama.call_args[1]
        assert call_kwargs["mirostat"] == 1
        assert call_kwargs["mirostat_eta"] == 0.1
        assert call_kwargs["mirostat_tau"] == 5.0
        assert model == mock_instance

    @patch("lfx.components.ollama.ollama.ChatOllama")
    async def test_build_model_with_mirostat_2_enabled(self, mock_chat_ollama, component_class):
        """Test that mirostat parameters are included when Mirostat 2.0 is enabled."""
        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance

        component = component_class(
            base_url="http://localhost:11434",
            model_name="ollama-model",
            mirostat="Mirostat 2.0",  # Setting to Mirostat 2.0 (value 2)
            mirostat_eta=0.2,
            mirostat_tau=10.0,
            temperature=0.1,
        )
        model = component.build_model()
        # Verify that mirostat and its related params ARE passed
        call_kwargs = mock_chat_ollama.call_args[1]
        assert call_kwargs["mirostat"] == 2
        assert call_kwargs["mirostat_eta"] == 0.2
        assert call_kwargs["mirostat_tau"] == 10.0
        assert model == mock_instance

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
        # Should not raise an error, just set empty options
        updated_config = await component.update_build_config(build_config, field_value, field_name)
        assert updated_config["model_name"]["options"] == []

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

    @pytest.mark.integration
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

    @patch("lfx.components.ollama.ollama.ChatOllama")
    @patch("lfx.components.ollama.ollama.logger")
    def test_build_model_strips_v1_suffix_and_logs_warning(self, mock_logger, mock_chat_ollama):
        """Test that /v1 suffix is automatically stripped and a warning is logged."""
        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        component = ChatOllamaComponent()
        component.base_url = "http://localhost:11434/v1"
        component.model_name = "llama3.1"
        component.mirostat = "Disabled"

        model = component.build_model()

        # Verify warning was logged
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Detected '/v1' suffix in base URL" in warning_message
        assert "https://docs.ollama.com/openai#openai-compatibility" in warning_message

        # Verify ChatOllama was called without /v1
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["base_url"] == "http://localhost:11434"
        assert model == mock_model

    @patch("lfx.components.ollama.ollama.ChatOllama")
    @patch("lfx.components.ollama.ollama.logger")
    def test_build_model_strips_v1_trailing_slash(self, mock_logger, mock_chat_ollama):
        """Test that /v1/ suffix is also automatically stripped."""
        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        component = ChatOllamaComponent()
        component.base_url = "http://localhost:11434/v1/"
        component.model_name = "llama3.1"
        component.mirostat = "Disabled"

        model = component.build_model()

        # Verify warning was logged
        mock_logger.warning.assert_called_once()

        # Verify ChatOllama was called without /v1
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["base_url"] == "http://localhost:11434"
        assert model == mock_model

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.get")
    async def test_is_valid_ollama_url_with_v1_suffix(self, mock_get):
        """Test that is_valid_ollama_url strips /v1 suffix when validating."""
        component = ChatOllamaComponent()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = await component.is_valid_ollama_url("http://localhost:11434/v1")

        # Verify it called /api/tags without /v1
        mock_get.assert_called_once()
        called_kwargs = mock_get.call_args[1]
        assert called_kwargs["url"] == "http://localhost:11434/api/tags"
        assert result is True

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.get")
    async def test_get_models_with_v1_suffix(self, mock_get, mock_post):
        """Test that get_models strips /v1 suffix when fetching models."""
        component = ChatOllamaComponent()
        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "model1"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.return_value = {component.JSON_CAPABILITIES_KEY: [component.DESIRED_CAPABILITY]}
        mock_post.return_value = mock_post_response

        base_url = "http://localhost:11434/v1"
        result = await component.get_models(base_url)

        # Verify it called /api/tags without /v1
        assert mock_get.call_count == 1
        called_kwargs = mock_get.call_args[1]
        assert called_kwargs["url"] == "http://localhost:11434/api/tags"
        assert result == ["model1"]

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.get")
    async def test_update_build_config_no_error_when_ollama_not_running(self, mock_get):
        """Test that update_build_config doesn't throw error when Ollama isn't running."""
        import httpx

        component = ChatOllamaComponent()
        mock_get.side_effect = httpx.RequestError("Connection error", request=None)

        build_config = {
            "base_url": {"load_from_db": False, "value": "http://localhost:11434"},
            "model_name": {"options": []},
            "tool_model_enabled": {"value": False},
            "api_key": {"value": None, "advanced": True},
        }
        field_value = "http://localhost:11434"
        field_name = "base_url"
        component.base_url = "http://localhost:11434"

        # Should not raise an error, just set empty options
        updated_config = await component.update_build_config(build_config, field_value, field_name)
        assert updated_config["model_name"]["options"] == []

    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_with_json_format_string(self, mock_chat_ollama, component_class, default_kwargs):
        """Test that the format field works with 'json' string value (backward compatibility)."""
        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance

        # Use default_kwargs which has format="json"
        component = component_class(**default_kwargs)
        model = component.build_model()

        # Verify ChatOllama was called with format="json"
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["format"] == "json"
        assert model == mock_instance

    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_with_json_schema_dict(self, mock_chat_ollama, component_class, default_kwargs):
        """Test that the format field works with a JSON schema dictionary."""
        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance

        # Define a simple JSON schema
        json_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"],
        }

        # Override format with the JSON schema dict
        kwargs = default_kwargs.copy()
        kwargs["format"] = json_schema

        component = component_class(**kwargs)
        model = component.build_model()

        # Verify ChatOllama was called with the JSON schema dict
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["format"] == json_schema
        assert call_args["format"]["type"] == "object"
        assert "name" in call_args["format"]["properties"]
        assert "age" in call_args["format"]["properties"]
        assert call_args["format"]["required"] == ["name"]
        assert model == mock_instance

    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_with_complex_json_schema(self, mock_chat_ollama, component_class, default_kwargs):
        """Test that the format field works with a complex/realistic JSON schema (e.g., from Pydantic)."""
        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance

        # Simulate a more complex schema like one generated by Pydantic's model_json_schema()
        complex_schema = {
            "type": "object",
            "title": "Person",
            "properties": {
                "name": {"type": "string", "description": "The person's full name"},
                "age": {"type": "integer", "minimum": 0, "maximum": 150},
                "email": {"type": "string", "format": "email"},
                "address": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                        "zipcode": {"type": "string", "pattern": "^[0-9]{5}$"},
                    },
                    "required": ["city"],
                },
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "email"],
            "additionalProperties": False,
        }

        # Override format with the complex JSON schema
        kwargs = default_kwargs.copy()
        kwargs["format"] = complex_schema

        component = component_class(**kwargs)
        model = component.build_model()

        # Verify ChatOllama was called with the complex schema
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["format"] == complex_schema
        assert call_args["format"]["title"] == "Person"
        assert call_args["format"]["properties"]["address"]["type"] == "object"
        assert call_args["format"]["required"] == ["name", "email"]
        assert call_args["format"]["additionalProperties"] is False
        assert model == mock_instance

    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_with_pydantic_model_json_schema(self, mock_chat_ollama, component_class, default_kwargs):
        """Test that the format field works with a schema generated from Pydantic's model_json_schema() method.

        This test reproduces the exact use case described in issue #7122:
        https://github.com/langflow-ai/langflow/issues/7122
        """
        from pydantic import BaseModel, Field

        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance

        # Create a Pydantic model exactly as a user would
        class PersonInfo(BaseModel):
            """Information about a person."""

            name: str = Field(description="The person's full name")
            age: int = Field(ge=0, le=150, description="The person's age")
            email: str = Field(description="Email address")
            city: str = Field(description="City of residence")

        # Generate the schema using Pydantic's model_json_schema() as mentioned in the issue
        pydantic_schema = PersonInfo.model_json_schema()

        # Override format with the Pydantic-generated schema
        kwargs = default_kwargs.copy()
        kwargs["format"] = pydantic_schema

        component = component_class(**kwargs)

        # This should NOT raise an exception (was the bug in issue #7122)
        model = component.build_model()

        # Verify ChatOllama was called with the Pydantic-generated schema
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["format"] == pydantic_schema
        assert call_args["format"]["type"] == "object"
        assert "name" in call_args["format"]["properties"]
        assert "age" in call_args["format"]["properties"]
        assert "email" in call_args["format"]["properties"]
        assert "city" in call_args["format"]["properties"]
        assert call_args["format"]["properties"]["name"]["description"] == "The person's full name"
        assert model == mock_instance

    @pytest.mark.asyncio
    async def test_parse_json_response_valid_dict(self, component_class, default_kwargs):
        """Test _parse_json_response with valid JSON dict response."""
        mock_message = MagicMock()
        mock_message.text = '{"name": "John", "age": 30}'

        component = component_class(**default_kwargs)
        component.text_response = AsyncMock(return_value=mock_message)

        result = await component._parse_json_response()

        assert result == {"name": "John", "age": 30}
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_parse_json_response_valid_list(self, component_class, default_kwargs):
        """Test _parse_json_response with valid JSON list response."""
        mock_message = MagicMock()
        mock_message.text = '[{"id": 1}, {"id": 2}]'

        component = component_class(**default_kwargs)
        component.text_response = AsyncMock(return_value=mock_message)

        result = await component._parse_json_response()

        assert result == [{"id": 1}, {"id": 2}]
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_parse_json_response_invalid_json(self, component_class, default_kwargs):
        """Test _parse_json_response with invalid JSON raises ValueError."""
        mock_message = MagicMock()
        mock_message.text = "This is not JSON"

        component = component_class(**default_kwargs)
        component.text_response = AsyncMock(return_value=mock_message)

        with pytest.raises(ValueError, match="Invalid JSON response"):
            await component._parse_json_response()

    @pytest.mark.asyncio
    async def test_parse_json_response_empty_response(self, component_class, default_kwargs):
        """Test _parse_json_response with empty response raises ValueError."""
        mock_message = MagicMock()
        mock_message.text = ""

        component = component_class(**default_kwargs)
        component.text_response = AsyncMock(return_value=mock_message)

        with pytest.raises(ValueError, match="No response from model"):
            await component._parse_json_response()

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllamaComponent._parse_json_response")
    async def test_build_data_output_with_dict(self, mock_parse_json, component_class, default_kwargs):
        """Test build_data_output with dict response."""
        mock_parse_json.return_value = {"name": "Alice", "city": "NYC"}

        component = component_class(**default_kwargs)
        result = await component.build_data_output()

        assert isinstance(result, Data)
        assert result.data == {"name": "Alice", "city": "NYC"}

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllamaComponent._parse_json_response")
    async def test_build_data_output_with_list_single_item(self, mock_parse_json, component_class, default_kwargs):
        """Test build_data_output with single-item list response."""
        mock_parse_json.return_value = [{"id": 1, "value": "test"}]

        component = component_class(**default_kwargs)
        result = await component.build_data_output()

        assert isinstance(result, Data)
        assert result.data == {"id": 1, "value": "test"}

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllamaComponent._parse_json_response")
    async def test_build_data_output_with_list_multiple_items(self, mock_parse_json, component_class, default_kwargs):
        """Test build_data_output with multiple-item list response."""
        mock_parse_json.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]

        component = component_class(**default_kwargs)
        result = await component.build_data_output()

        assert isinstance(result, Data)
        assert result.data == {"results": [{"id": 1}, {"id": 2}, {"id": 3}]}

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllamaComponent._parse_json_response")
    async def test_build_data_output_with_primitive(self, mock_parse_json, component_class, default_kwargs):
        """Test build_data_output with primitive value response."""
        mock_parse_json.return_value = "simple string"

        component = component_class(**default_kwargs)
        result = await component.build_data_output()

        assert isinstance(result, Data)
        assert result.data == {"value": "simple string"}

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllamaComponent._parse_json_response")
    async def test_build_dataframe_output_with_list_of_dicts(self, mock_parse_json, component_class, default_kwargs):
        """Test build_dataframe_output with list of dicts."""
        mock_parse_json.return_value = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]

        component = component_class(**default_kwargs)
        result = await component.build_dataframe_output()

        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert list(result.columns) == ["name", "age"]

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllamaComponent._parse_json_response")
    async def test_build_dataframe_output_with_empty_list(self, mock_parse_json, component_class, default_kwargs):
        """Test build_dataframe_output with empty list."""
        mock_parse_json.return_value = []

        component = component_class(**default_kwargs)
        result = await component.build_dataframe_output()

        assert isinstance(result, DataFrame)
        assert len(result) == 0

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllamaComponent._parse_json_response")
    async def test_build_dataframe_output_with_single_dict(self, mock_parse_json, component_class, default_kwargs):
        """Test build_dataframe_output with single dict."""
        mock_parse_json.return_value = {"name": "Charlie", "score": 95}

        component = component_class(**default_kwargs)
        result = await component.build_dataframe_output()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["name"] == "Charlie"
        assert result.iloc[0]["score"] == 95

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllamaComponent._parse_json_response")
    async def test_build_dataframe_output_with_primitive(self, mock_parse_json, component_class, default_kwargs):
        """Test build_dataframe_output with primitive value."""
        mock_parse_json.return_value = 42

        component = component_class(**default_kwargs)
        result = await component.build_dataframe_output()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["value"] == 42

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllamaComponent._parse_json_response")
    async def test_build_dataframe_output_with_invalid_list(self, mock_parse_json, component_class, default_kwargs):
        """Test build_dataframe_output with list of non-dicts raises ValueError."""
        mock_parse_json.return_value = [1, 2, 3, "string"]

        component = component_class(**default_kwargs)

        with pytest.raises(ValueError, match="List items must be dictionaries"):
            await component.build_dataframe_output()

    def test_headers_with_cloud_url_no_api_key(self):
        """Test that headers return None when cloud URL but no API key."""
        component = ChatOllamaComponent()
        component.base_url = DEFAULT_OLLAMA_API_URL
        component.api_key = None

        headers = component.headers
        assert headers is None

    def test_headers_with_cloud_url_and_api_key(self):
        """Test that headers include Authorization for cloud URL with API key."""
        component = ChatOllamaComponent()
        component.base_url = DEFAULT_OLLAMA_API_URL
        component.api_key = "test-api-key-12345"

        headers = component.headers
        assert headers is not None
        assert headers["Authorization"] == "Bearer test-api-key-12345"

    def test_headers_with_local_url_no_api_key(self):
        """Test that headers return None for local URLs without API key."""
        component = ChatOllamaComponent()
        component.base_url = "http://localhost:11434"
        component.api_key = None

        headers = component.headers
        assert headers is None

    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_with_cloud_api_and_headers(self, mock_chat_ollama):
        """Test that build_model passes headers for cloud API with API key."""
        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        component = ChatOllamaComponent()
        component.base_url = DEFAULT_OLLAMA_API_URL
        component.api_key = "test-cloud-api-key"
        component.model_name = "qwen3-coder:480b-cloud"
        component.mirostat = "Disabled"
        component.temperature = 0.7

        model = component.build_model()

        # Verify client_kwargs with headers were passed
        call_args = mock_chat_ollama.call_args[1]
        assert "client_kwargs" in call_args
        assert "headers" in call_args["client_kwargs"]
        assert call_args["client_kwargs"]["headers"]["Authorization"] == "Bearer test-cloud-api-key"
        assert call_args["base_url"] == DEFAULT_OLLAMA_API_URL
        assert model == mock_model

    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_with_cloud_api_no_headers(self, mock_chat_ollama):
        """Test that build_model works for cloud API without API key."""
        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        component = ChatOllamaComponent()
        component.base_url = DEFAULT_OLLAMA_API_URL
        component.api_key = None
        component.model_name = "deepseek-v3.1:671b-cloud"
        component.mirostat = "Disabled"

        model = component.build_model()

        # When headers is None, client_kwargs should not be passed
        call_args = mock_chat_ollama.call_args[1]
        assert "client_kwargs" not in call_args
        assert model == mock_model

    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_local_no_headers(self, mock_chat_ollama):
        """Test that build_model doesn't pass headers for local instances."""
        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        component = ChatOllamaComponent()
        component.base_url = "http://localhost:11434"
        component.api_key = None
        component.model_name = "llama3.1"
        component.mirostat = "Disabled"

        model = component.build_model()

        # Verify no client_kwargs were passed
        call_args = mock_chat_ollama.call_args[1]
        assert "client_kwargs" not in call_args
        assert model == mock_model

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.get")
    async def test_is_valid_ollama_url_with_cloud_and_headers(self, mock_get):
        """Test that is_valid_ollama_url passes headers for cloud URL."""
        component = ChatOllamaComponent()
        component.base_url = DEFAULT_OLLAMA_API_URL
        component.api_key = "test-cloud-api-key"

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = await component.is_valid_ollama_url(DEFAULT_OLLAMA_API_URL)

        # Verify headers were passed
        assert mock_get.call_count == 1
        call_kwargs = mock_get.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-cloud-api-key"
        assert result is True

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.get")
    async def test_is_valid_ollama_url_local_no_headers(self, mock_get):
        """Test that is_valid_ollama_url doesn't pass headers for local URL."""
        component = ChatOllamaComponent()
        component.base_url = "http://localhost:11434"
        component.api_key = None

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = await component.is_valid_ollama_url("http://localhost:11434")

        # Verify headers were None
        assert mock_get.call_count == 1
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["headers"] is None
        assert result is True

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.get")
    async def test_get_models_with_cloud_and_headers(self, mock_get, mock_post):
        """Test that get_models passes headers for cloud API."""
        component = ChatOllamaComponent()
        component.base_url = DEFAULT_OLLAMA_API_URL
        component.api_key = "test-cloud-api-key"

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "deepseek-v3.1:671b-cloud"},
                {component.JSON_NAME_KEY: "qwen3-coder:480b-cloud"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.side_effect = [
            {component.JSON_CAPABILITIES_KEY: [component.DESIRED_CAPABILITY]},
            {component.JSON_CAPABILITIES_KEY: [component.DESIRED_CAPABILITY]},
        ]
        mock_post.return_value = mock_post_response

        result = await component.get_models(DEFAULT_OLLAMA_API_URL)

        # Verify headers were passed to both GET and POST
        assert mock_get.call_count == 1
        get_call_kwargs = mock_get.call_args[1]
        assert "headers" in get_call_kwargs
        assert get_call_kwargs["headers"]["Authorization"] == "Bearer test-cloud-api-key"

        assert mock_post.call_count == 2
        post_call_kwargs = mock_post.call_args[1]
        assert "headers" in post_call_kwargs
        assert post_call_kwargs["headers"]["Authorization"] == "Bearer test-cloud-api-key"

        assert result == ["deepseek-v3.1:671b-cloud", "qwen3-coder:480b-cloud"]

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama.httpx.AsyncClient.get")
    async def test_get_models_local_no_headers(self, mock_get, mock_post):
        """Test that get_models doesn't pass headers for local instances (when api key is not provided)."""
        component = ChatOllamaComponent()
        component.base_url = "http://localhost:11434"
        component.api_key = None

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "llama3.1"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.return_value = {component.JSON_CAPABILITIES_KEY: [component.DESIRED_CAPABILITY]}
        mock_post.return_value = mock_post_response

        result = await component.get_models("http://localhost:11434")

        # Verify headers were None for both GET and POST
        assert mock_get.call_count == 1
        get_call_kwargs = mock_get.call_args[1]
        assert get_call_kwargs["headers"] is None

        assert mock_post.call_count == 1
        post_call_kwargs = mock_post.call_args[1]
        assert post_call_kwargs["headers"] is None

        assert result == ["llama3.1"]

    def test_get_base_url_cloud_no_transform(self):
        """Test that cloud URL is not transformed."""
        from lfx.utils.util import transform_localhost_url

        result = transform_localhost_url(DEFAULT_OLLAMA_API_URL)
        assert result == DEFAULT_OLLAMA_API_URL

    @patch("lfx.components.ollama.ollama.ChatOllama")
    def test_build_model_cloud_with_v1_suffix_stripped(self, mock_chat_ollama):
        """Test that /v1 suffix is stripped from cloud URL."""
        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        component = ChatOllamaComponent()
        component.base_url = f"{DEFAULT_OLLAMA_API_URL}/v1"
        component.api_key = "test-key"
        component.model_name = "gpt-oss:20b-cloud"
        component.mirostat = "Disabled"

        model = component.build_model()

        # Verify /v1 was stripped
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["base_url"] == DEFAULT_OLLAMA_API_URL
        assert "/v1" not in call_args["base_url"]
        assert model == mock_model
