"""Tests for OllamaEmbeddingsComponent.

This test module validates the OllamaEmbeddingsComponent functionality:
- Building embeddings with various configurations
- URL handling (localhost transformation, /v1 suffix stripping)
- Model fetching with capability filtering
- URL validation
- Build config updates
- Headers property behavior
"""

import re
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from lfx.components.ollama.ollama_embeddings import OllamaEmbeddingsComponent

from tests.base import ComponentTestBaseWithoutClient


class TestOllamaEmbeddingsComponent(ComponentTestBaseWithoutClient):
    """Tests for the OllamaEmbeddingsComponent."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return OllamaEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "base_url": "http://localhost:11434",
            "model_name": "nomic-embed-text",
            "api_key": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        # Provide an empty list or the actual mapping if versioned files exist
        return []

    # =========================================================================
    # Headers Property Tests
    # =========================================================================

    def test_headers_with_api_key(self, component_class):
        """Test that headers include Authorization when API key is provided."""
        component = component_class()
        component.api_key = "test-api-key-12345"

        headers = component.headers
        assert headers is not None
        assert headers["Authorization"] == "Bearer test-api-key-12345"

    def test_headers_without_api_key(self, component_class):
        """Test that headers return None when no API key is provided."""
        component = component_class()
        component.api_key = None

        headers = component.headers
        assert headers is None

    def test_headers_with_empty_api_key(self, component_class):
        """Test that headers return None when API key is empty string."""
        component = component_class()
        component.api_key = ""

        headers = component.headers
        assert headers is None

    def test_headers_with_whitespace_api_key(self, component_class):
        """Test that headers return None when API key is whitespace only."""
        component = component_class()
        component.api_key = "   "

        headers = component.headers
        assert headers is None

    # =========================================================================
    # Build Embeddings Tests
    # =========================================================================

    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    def test_build_embeddings_basic(self, mock_ollama_embeddings, component_class, default_kwargs):
        """Test build_embeddings with basic parameters."""
        mock_instance = MagicMock()
        mock_ollama_embeddings.return_value = mock_instance

        component = component_class(**default_kwargs)
        result = component.build_embeddings()

        mock_ollama_embeddings.assert_called_once_with(
            model="nomic-embed-text",
            base_url="http://localhost:11434",
        )
        assert result == mock_instance

    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    def test_build_embeddings_with_api_key(self, mock_ollama_embeddings, component_class):
        """Test build_embeddings passes headers via client_kwargs when API key is set."""
        mock_instance = MagicMock()
        mock_ollama_embeddings.return_value = mock_instance

        component = component_class()
        component.base_url = "http://localhost:11434"
        component.model_name = "nomic-embed-text"
        component.api_key = "test-api-key"

        result = component.build_embeddings()

        mock_ollama_embeddings.assert_called_once_with(
            model="nomic-embed-text",
            base_url="http://localhost:11434",
            client_kwargs={"headers": {"Authorization": "Bearer test-api-key"}},
        )
        assert result == mock_instance

    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    def test_build_embeddings_without_api_key_no_client_kwargs(self, mock_ollama_embeddings, component_class):
        """Test build_embeddings doesn't pass client_kwargs when no API key."""
        mock_instance = MagicMock()
        mock_ollama_embeddings.return_value = mock_instance

        component = component_class()
        component.base_url = "http://localhost:11434"
        component.model_name = "nomic-embed-text"
        component.api_key = None

        component.build_embeddings()

        # Verify client_kwargs is not in the call
        call_kwargs = mock_ollama_embeddings.call_args[1]
        assert "client_kwargs" not in call_kwargs

    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    def test_build_embeddings_connection_error(self, mock_ollama_embeddings, component_class):
        """Test build_embeddings raises ValueError on connection error."""
        mock_ollama_embeddings.side_effect = Exception("connection error")

        component = component_class()
        component.base_url = "http://localhost:11434"
        component.model_name = "nomic-embed-text"
        component.api_key = None

        with pytest.raises(ValueError, match=re.escape("Unable to connect to the Ollama API.")):
            component.build_embeddings()

    # =========================================================================
    # URL Handling Tests - /v1 Suffix Stripping
    # =========================================================================

    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    @patch("lfx.components.ollama.ollama_embeddings.logger")
    def test_build_embeddings_strips_v1_suffix_and_logs_warning(
        self, mock_logger, mock_ollama_embeddings, component_class
    ):
        """Test that /v1 suffix is automatically stripped and a warning is logged."""
        mock_instance = MagicMock()
        mock_ollama_embeddings.return_value = mock_instance

        component = component_class()
        component.base_url = "http://localhost:11434/v1"
        component.model_name = "nomic-embed-text"
        component.api_key = None

        component.build_embeddings()

        # Verify warning was logged
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Detected '/v1' suffix in base URL" in warning_message
        assert "https://docs.ollama.com/openai#openai-compatibility" in warning_message

        # Verify OllamaEmbeddings was called without /v1
        call_kwargs = mock_ollama_embeddings.call_args[1]
        assert call_kwargs["base_url"] == "http://localhost:11434"

    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    @patch("lfx.components.ollama.ollama_embeddings.logger")
    def test_build_embeddings_strips_v1_trailing_slash(self, mock_logger, mock_ollama_embeddings, component_class):
        """Test that /v1/ suffix is also automatically stripped."""
        mock_instance = MagicMock()
        mock_ollama_embeddings.return_value = mock_instance

        component = component_class()
        component.base_url = "http://localhost:11434/v1/"
        component.model_name = "nomic-embed-text"
        component.api_key = None

        component.build_embeddings()

        # Verify warning was logged
        mock_logger.warning.assert_called_once()

        # Verify OllamaEmbeddings was called without /v1
        call_kwargs = mock_ollama_embeddings.call_args[1]
        assert call_kwargs["base_url"] == "http://localhost:11434"

    # =========================================================================
    # URL Handling Tests - Localhost Transformation
    # =========================================================================

    @patch("socket.getaddrinfo")
    @patch("lfx.utils.util.Path")
    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    def test_build_embeddings_transforms_localhost_in_docker_container(
        self, mock_ollama_embeddings, mock_path_class, mock_getaddrinfo, component_class
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
        mock_ollama_embeddings.return_value = mock_model

        component = component_class()
        component.base_url = "http://localhost:11434"
        component.model_name = "nomic-embed-text"
        component.api_key = None

        result = component.build_embeddings()

        # Verify OllamaEmbeddings was called with host.docker.internal
        call_kwargs = mock_ollama_embeddings.call_args[1]
        assert call_kwargs["base_url"] == "http://host.docker.internal:11434"
        assert result == mock_model

    @patch("lfx.utils.util.Path")
    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    def test_build_embeddings_no_transform_outside_container(
        self, mock_ollama_embeddings, mock_path_class, component_class
    ):
        """Test that localhost URLs are NOT transformed when running outside a container."""
        # Mock no container environment
        mock_instance = MagicMock()
        mock_instance.exists.return_value = False
        mock_path_class.return_value = mock_instance

        mock_model = MagicMock()
        mock_ollama_embeddings.return_value = mock_model

        component = component_class()
        component.base_url = "http://localhost:11434"
        component.model_name = "nomic-embed-text"
        component.api_key = None

        result = component.build_embeddings()

        # Verify OllamaEmbeddings was called with original localhost URL
        call_kwargs = mock_ollama_embeddings.call_args[1]
        assert call_kwargs["base_url"] == "http://localhost:11434"
        assert result == mock_model

    @patch("socket.getaddrinfo")
    @patch("lfx.utils.util.Path")
    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    def test_build_embeddings_transforms_localhost_in_podman_container(
        self, mock_ollama_embeddings, mock_path_class, mock_getaddrinfo, component_class
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
        mock_ollama_embeddings.return_value = mock_model

        component = component_class()
        component.base_url = "http://localhost:11434"
        component.model_name = "nomic-embed-text"
        component.api_key = None

        result = component.build_embeddings()

        # Verify OllamaEmbeddings was called with host.containers.internal
        call_kwargs = mock_ollama_embeddings.call_args[1]
        assert call_kwargs["base_url"] == "http://host.containers.internal:11434"
        assert result == mock_model

    @patch("socket.getaddrinfo")
    @patch("lfx.utils.util.Path")
    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    def test_build_embeddings_transforms_127_0_0_1_in_container(
        self, mock_ollama_embeddings, mock_path_class, mock_getaddrinfo, component_class
    ):
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
        mock_ollama_embeddings.return_value = mock_model

        component = component_class()
        component.base_url = "http://127.0.0.1:11434"
        component.model_name = "nomic-embed-text"
        component.api_key = None

        result = component.build_embeddings()

        # Verify OllamaEmbeddings was called with host.docker.internal
        call_kwargs = mock_ollama_embeddings.call_args[1]
        assert call_kwargs["base_url"] == "http://host.docker.internal:11434"
        assert result == mock_model

    # =========================================================================
    # Model Fetching Tests (async)
    # =========================================================================

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_success_filters_embedding_capability(self, mock_get, mock_post, component_class):
        """Test get_model returns only models with embedding capability."""
        component = component_class()

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "nomic-embed-text"},
                {component.JSON_NAME_KEY: "llama3.1"},
                {component.JSON_NAME_KEY: "mxbai-embed-large"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        # First model has embedding capability, second doesn't, third does
        mock_post_response.json.side_effect = [
            {component.JSON_CAPABILITIES_KEY: [component.EMBEDDING_CAPABILITY]},
            {component.JSON_CAPABILITIES_KEY: ["completion"]},  # Not an embedding model
            {component.JSON_CAPABILITIES_KEY: [component.EMBEDDING_CAPABILITY, "completion"]},
        ]
        mock_post.return_value = mock_post_response

        base_url = "http://localhost:11434"
        result = await component.get_model(base_url)

        # Should only return embedding models
        assert result == ["nomic-embed-text", "mxbai-embed-large"]
        assert mock_get.call_count == 1
        assert mock_post.call_count == 3

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_failure(self, mock_get, component_class):
        """Test get_model raises ValueError on connection error."""
        import httpx

        component = component_class()
        mock_get.side_effect = httpx.RequestError("Connection error", request=None)

        base_url = "http://localhost:11434"
        with pytest.raises(ValueError, match=re.escape("Could not get model names from Ollama.")):
            await component.get_model(base_url)

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_with_v1_suffix_stripped(self, mock_get, mock_post, component_class):
        """Test that get_model strips /v1 suffix when fetching models."""
        component = component_class()

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "nomic-embed-text"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.return_value = {component.JSON_CAPABILITIES_KEY: [component.EMBEDDING_CAPABILITY]}
        mock_post.return_value = mock_post_response

        base_url = "http://localhost:11434/v1"
        result = await component.get_model(base_url)

        # Verify it called /api/tags without /v1
        assert mock_get.call_count == 1
        called_kwargs = mock_get.call_args[1]
        assert called_kwargs["url"] == "http://localhost:11434/api/tags"
        assert result == ["nomic-embed-text"]

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_with_api_key_passes_headers(self, mock_get, mock_post, component_class):
        """Test that get_model passes headers when API key is set."""
        component = component_class()
        component.api_key = "test-api-key"

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "nomic-embed-text"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.return_value = {component.JSON_CAPABILITIES_KEY: [component.EMBEDDING_CAPABILITY]}
        mock_post.return_value = mock_post_response

        base_url = "http://localhost:11434"
        result = await component.get_model(base_url)

        # Verify headers were passed to both GET and POST
        get_call_kwargs = mock_get.call_args[1]
        assert get_call_kwargs["headers"]["Authorization"] == "Bearer test-api-key"

        post_call_kwargs = mock_post.call_args[1]
        assert post_call_kwargs["headers"]["Authorization"] == "Bearer test-api-key"

        assert result == ["nomic-embed-text"]

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_empty_model_list(self, mock_get, component_class):
        """Test get_model returns empty list when no models are available."""
        component = component_class()

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {component.JSON_MODELS_KEY: []}
        mock_get.return_value = mock_get_response

        base_url = "http://localhost:11434"
        result = await component.get_model(base_url)

        assert result == []
        assert mock_get.call_count == 1

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_missing_capabilities_key(self, mock_get, mock_post, component_class):
        """Test get_model handles models with missing capabilities key (defaults to empty list)."""
        component = component_class()

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "model-without-caps"},
                {component.JSON_NAME_KEY: "embedding-model"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        # First model has no capabilities key, second has embedding capability
        mock_post_response.json.side_effect = [
            {},  # No capabilities key at all
            {component.JSON_CAPABILITIES_KEY: [component.EMBEDDING_CAPABILITY]},
        ]
        mock_post.return_value = mock_post_response

        base_url = "http://localhost:11434"
        result = await component.get_model(base_url)

        # Should only return the model with embedding capability
        assert result == ["embedding-model"]
        assert mock_post.call_count == 2

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_without_api_key_no_headers(self, mock_get, mock_post, component_class):
        """Test that get_model passes None headers when no API key is set."""
        component = component_class()
        component.api_key = None

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "nomic-embed-text"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.return_value = {component.JSON_CAPABILITIES_KEY: [component.EMBEDDING_CAPABILITY]}
        mock_post.return_value = mock_post_response

        base_url = "http://localhost:11434"
        result = await component.get_model(base_url)

        # Verify headers were None for both GET and POST
        get_call_kwargs = mock_get.call_args[1]
        assert get_call_kwargs["headers"] is None

        post_call_kwargs = mock_post.call_args[1]
        assert post_call_kwargs["headers"] is None

        assert result == ["nomic-embed-text"]

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_url_normalization_trailing_slash(self, mock_get, mock_post, component_class):
        """Test that get_model normalizes URLs with trailing slashes."""
        component = component_class()

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "nomic-embed-text"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.return_value = {component.JSON_CAPABILITIES_KEY: [component.EMBEDDING_CAPABILITY]}
        mock_post.return_value = mock_post_response

        # Test with trailing slash
        base_url = "http://localhost:11434/"
        result = await component.get_model(base_url)

        # Verify it called the correct URL
        assert mock_get.call_count == 1
        called_kwargs = mock_get.call_args[1]
        assert called_kwargs["url"] == "http://localhost:11434/api/tags"
        assert result == ["nomic-embed-text"]

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_url_normalization_v1_trailing_slash(self, mock_get, mock_post, component_class):
        """Test that get_model normalizes URLs with /v1/ (trailing slash after v1)."""
        component = component_class()

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "nomic-embed-text"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.return_value = {component.JSON_CAPABILITIES_KEY: [component.EMBEDDING_CAPABILITY]}
        mock_post.return_value = mock_post_response

        # Test with /v1/ (trailing slash after v1)
        base_url = "http://localhost:11434/v1/"
        result = await component.get_model(base_url)

        # Verify it called the correct URL without /v1
        assert mock_get.call_count == 1
        called_kwargs = mock_get.call_args[1]
        assert called_kwargs["url"] == "http://localhost:11434/api/tags"
        assert result == ["nomic-embed-text"]

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_all_models_non_embedding(self, mock_get, mock_post, component_class):
        """Test get_model returns empty list when no models have embedding capability."""
        component = component_class()

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "llama3.1"},
                {component.JSON_NAME_KEY: "codellama"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        # All models have completion capability only, no embedding
        mock_post_response.json.side_effect = [
            {component.JSON_CAPABILITIES_KEY: ["completion"]},
            {component.JSON_CAPABILITIES_KEY: ["completion", "tools"]},
        ]
        mock_post.return_value = mock_post_response

        base_url = "http://localhost:11434"
        result = await component.get_model(base_url)

        # Should return empty list since no embedding models
        assert result == []
        assert mock_post.call_count == 2

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_post_request_failure(self, mock_get, mock_post, component_class):
        """Test get_model raises ValueError when POST request to get capabilities fails."""
        import httpx

        component = component_class()

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "nomic-embed-text"},
            ]
        }
        mock_get.return_value = mock_get_response

        # POST request fails
        mock_post.side_effect = httpx.RequestError("Connection error", request=None)

        base_url = "http://localhost:11434"
        with pytest.raises(ValueError, match=re.escape("Could not get model names from Ollama.")):
            await component.get_model(base_url)

    # =========================================================================
    # URL Validation Tests (async)
    # =========================================================================

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_is_valid_ollama_url_success(self, mock_get, component_class):
        """Test is_valid_ollama_url returns True for valid URL."""
        component = component_class()

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = await component.is_valid_ollama_url("http://localhost:11434")

        assert result is True
        mock_get.assert_called_once()

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_is_valid_ollama_url_failure(self, mock_get, component_class):
        """Test is_valid_ollama_url returns False on connection error."""
        import httpx

        component = component_class()
        mock_get.side_effect = httpx.RequestError("Connection error", request=None)

        result = await component.is_valid_ollama_url("http://localhost:11434")

        assert result is False

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_is_valid_ollama_url_with_v1_suffix(self, mock_get, component_class):
        """Test that is_valid_ollama_url strips /v1 suffix when validating."""
        component = component_class()

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
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_is_valid_ollama_url_with_api_key_passes_headers(self, mock_get, component_class):
        """Test that is_valid_ollama_url passes headers when API key is set."""
        component = component_class()
        component.api_key = "test-api-key"

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = await component.is_valid_ollama_url("http://localhost:11434")

        # Verify headers were passed
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-api-key"
        assert result is True

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_is_valid_ollama_url_without_api_key_no_headers(self, mock_get, component_class):
        """Test that is_valid_ollama_url doesn't pass headers when no API key."""
        component = component_class()
        component.api_key = None

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = await component.is_valid_ollama_url("http://localhost:11434")

        # Verify headers were None
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["headers"] is None
        assert result is True

    @pytest.mark.asyncio
    async def test_is_valid_ollama_url_with_empty_url(self, component_class):
        """Test that is_valid_ollama_url returns False for empty URL."""
        component = component_class()
        result = await component.is_valid_ollama_url("")

        assert result is False

    @pytest.mark.asyncio
    async def test_is_valid_ollama_url_with_none_url(self, component_class):
        """Test that is_valid_ollama_url returns False for None URL."""
        component = component_class()
        result = await component.is_valid_ollama_url(None)

        assert result is False

    # =========================================================================
    # Build Config Update Tests (async)
    # =========================================================================

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.post")
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_update_build_config_model_name_field(self, mock_get, mock_post, component_class):
        """Test update_build_config populates model options when model_name field is updated."""
        component = component_class()

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "nomic-embed-text"},
                {component.JSON_NAME_KEY: "mxbai-embed-large"},
            ]
        }
        mock_get.return_value = mock_get_response

        mock_post_response = AsyncMock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.side_effect = [
            {component.JSON_CAPABILITIES_KEY: [component.EMBEDDING_CAPABILITY]},
            {component.JSON_CAPABILITIES_KEY: [component.EMBEDDING_CAPABILITY]},
        ]
        mock_post.return_value = mock_post_response

        component.base_url = "http://localhost:11434"
        build_config = {
            "model_name": {"options": []},
        }

        # Mock is_valid_ollama_url to return True
        with patch.object(component, "is_valid_ollama_url", new_callable=AsyncMock) as mock_valid:
            mock_valid.return_value = True

            updated_config = await component.update_build_config(build_config, "nomic-embed-text", "model_name")

        assert "nomic-embed-text" in updated_config["model_name"]["options"]
        assert "mxbai-embed-large" in updated_config["model_name"]["options"]

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_update_build_config_base_url_field(self, mock_get, component_class):
        """Test update_build_config populates model options when base_url field is updated."""
        component = component_class()

        mock_get_response = AsyncMock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            component.JSON_MODELS_KEY: [
                {component.JSON_NAME_KEY: "nomic-embed-text"},
            ]
        }
        mock_get_response.status_code = 200
        mock_get.return_value = mock_get_response

        component.base_url = "http://localhost:11434"
        build_config = {
            "model_name": {"options": []},
        }

        # Mock both is_valid_ollama_url and get_model
        with (
            patch.object(component, "is_valid_ollama_url", new_callable=AsyncMock) as mock_valid,
            patch.object(component, "get_model", new_callable=AsyncMock) as mock_get_model,
        ):
            mock_valid.return_value = True
            mock_get_model.return_value = ["nomic-embed-text", "mxbai-embed-large"]

            updated_config = await component.update_build_config(build_config, "http://localhost:11434", "base_url")

        assert "nomic-embed-text" in updated_config["model_name"]["options"]
        assert "mxbai-embed-large" in updated_config["model_name"]["options"]

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_update_build_config_when_ollama_not_running(self, mock_get, component_class):
        """Test update_build_config raises error when Ollama isn't running."""
        import httpx

        component = component_class()
        mock_get.side_effect = httpx.RequestError("Connection error", request=None)

        component.base_url = "http://localhost:11434"
        build_config = {
            "model_name": {"options": []},
        }

        # Mock is_valid_ollama_url to return False
        with patch.object(component, "is_valid_ollama_url", new_callable=AsyncMock) as mock_valid:
            mock_valid.return_value = False

            with pytest.raises(ValueError, match="Ollama is not running"):
                await component.update_build_config(build_config, "nomic-embed-text", "model_name")

    @pytest.mark.asyncio
    async def test_update_build_config_empty_options_when_url_invalid(self, component_class):
        """Test update_build_config sets empty options when URL is invalid."""
        component = component_class()
        component.base_url = "http://localhost:11434"
        build_config = {
            "model_name": {"options": ["old-model"]},
        }

        # Mock is_valid_ollama_url to return True but get_model to fail gracefully
        with (
            patch.object(component, "is_valid_ollama_url", new_callable=AsyncMock) as mock_valid,
            patch.object(component, "get_model", new_callable=AsyncMock) as mock_get_model,
        ):
            mock_valid.return_value = True
            mock_get_model.return_value = []

            updated_config = await component.update_build_config(build_config, "http://localhost:11434", "base_url")

        assert updated_config["model_name"]["options"] == []

    # =========================================================================
    # Edge Cases and Integration Tests
    # =========================================================================

    def test_component_constants(self, component_class):
        """Test that component constants are correctly defined."""
        component = component_class()
        assert component.JSON_MODELS_KEY == "models"
        assert component.JSON_NAME_KEY == "name"
        assert component.JSON_CAPABILITIES_KEY == "capabilities"
        assert component.EMBEDDING_CAPABILITY == "embedding"

    def test_component_metadata(self, component_class):
        """Test that component metadata is correctly defined."""
        component = component_class()
        assert component.display_name == "Ollama Embeddings"
        assert component.name == "OllamaEmbeddings"
        assert component.icon == "Ollama"
        assert "embeddings" in component.description.lower()

    def test_component_inputs(self, component_class):
        """Test that component has expected inputs."""
        component = component_class()
        input_names = [inp.name for inp in component.inputs]
        assert "model_name" in input_names
        assert "base_url" in input_names
        assert "api_key" in input_names

    def test_component_outputs(self, component_class):
        """Test that component has expected outputs."""
        component = component_class()
        output_names = [out.name for out in component.outputs]
        assert "embeddings" in output_names
