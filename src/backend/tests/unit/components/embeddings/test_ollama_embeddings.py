import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.ollama.ollama_embeddings import OllamaEmbeddingsComponent

from tests.base import ComponentTestBaseWithoutClient


class TestOllamaEmbeddingsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return OllamaEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "base_url": "http://localhost:11434",
            "model_name": "nomic-embed-text",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    def test_build_embeddings(self, mock_ollama_embeddings, component_class, default_kwargs):
        mock_instance = MagicMock()
        mock_ollama_embeddings.return_value = mock_instance
        component = component_class(**default_kwargs)
        embeddings = component.build_embeddings()
        mock_ollama_embeddings.assert_called_once_with(
            model="nomic-embed-text",
            base_url="http://localhost:11434",
        )
        assert embeddings == mock_instance

    @patch("lfx.components.ollama.ollama_embeddings.OllamaEmbeddings")
    def test_build_embeddings_connection_error(self, mock_ollama_embeddings, component_class, default_kwargs):
        mock_ollama_embeddings.side_effect = Exception("connection error")
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match=re.escape("Unable to connect to the Ollama API.")):
            component.build_embeddings()

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_returns_all_models(self, mock_get):
        """Test that get_model returns all models without filtering."""
        component = OllamaEmbeddingsComponent()
        mock_response = AsyncMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "models": [
                {"name": "gemma3:4b"},
                {"name": "deepseek-r1:8b"},
                {"name": "nomic-embed-text"},
                {"name": "nomic-embed-text:latest"},
                {"name": "custom-embedding-model"},
            ]
        }
        mock_get.return_value = mock_response

        base_url = "http://localhost:11434"
        result = await component.get_model(base_url)

        # Should return all models, not just those matching hardcoded embedding model names
        assert len(result) == 5
        assert "gemma3:4b" in result
        assert "deepseek-r1:8b" in result
        assert "nomic-embed-text" in result
        assert "nomic-embed-text:latest" in result
        assert "custom-embedding-model" in result

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_handles_empty_models(self, mock_get):
        """Test that get_model handles empty model list."""
        component = OllamaEmbeddingsComponent()
        mock_response = AsyncMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"models": []}
        mock_get.return_value = mock_response

        base_url = "http://localhost:11434"
        result = await component.get_model(base_url)

        assert result == []

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_get_model_handles_request_error(self, mock_get):
        """Test that get_model handles request errors."""
        import httpx

        component = OllamaEmbeddingsComponent()
        mock_get.side_effect = httpx.RequestError("Connection error", request=None)

        base_url = "http://localhost:11434"
        with pytest.raises(ValueError, match=re.escape("Could not get model names from Ollama.")):
            await component.get_model(base_url)

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_update_build_config_updates_model_options(self, mock_get):
        """Test that update_build_config updates model options correctly."""
        component = OllamaEmbeddingsComponent()
        component.base_url = "http://localhost:11434"

        mock_response = AsyncMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "models": [
                {"name": "gemma3:4b"},
                {"name": "deepseek-r1:8b"},
            ]
        }
        mock_get.return_value = mock_response

        build_config = {
            "model_name": {"options": []},
        }
        field_value = None
        field_name = "model_name"

        updated_config = await component.update_build_config(build_config, field_value, field_name)

        assert updated_config["model_name"]["options"] == ["gemma3:4b", "deepseek-r1:8b"]

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_update_build_config_invalid_url(self, mock_get):
        """Test that update_build_config raises error for invalid URL."""
        import httpx

        component = OllamaEmbeddingsComponent()
        component.base_url = "http://invalid-url:11434"

        mock_get.side_effect = httpx.RequestError("Connection failed", request=None)

        build_config = {
            "model_name": {"options": []},
        }
        field_value = None
        field_name = "base_url"

        with pytest.raises(
            ValueError,
            match=re.escape("Ollama is not running on the provided base URL. Please start Ollama and try again."),
        ):
            await component.update_build_config(build_config, field_value, field_name)

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_is_valid_ollama_url(self, mock_get):
        """Test is_valid_ollama_url returns True for valid URL."""
        component = OllamaEmbeddingsComponent()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = await component.is_valid_ollama_url("http://localhost:11434")
        assert result is True

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama_embeddings.httpx.AsyncClient.get")
    async def test_is_valid_ollama_url_invalid(self, mock_get):
        """Test is_valid_ollama_url returns False for invalid URL."""
        import httpx

        component = OllamaEmbeddingsComponent()
        mock_get.side_effect = httpx.RequestError("Connection error", request=None)

        result = await component.is_valid_ollama_url("http://invalid-url:11434")
        assert result is False
