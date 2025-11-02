from unittest.mock import MagicMock, patch

import pytest
from lfx.components.models.embedding_model import (
    OLLAMA_EMBEDDING_MODELS,
    OPENAI_EMBEDDING_MODEL_NAMES,
    WATSONX_EMBEDDING_MODEL_NAMES,
    EmbeddingModelComponent,
)

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestEmbeddingModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return EmbeddingModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "provider": "OpenAI",
            "model": "text-embedding-3-small",
            "api_key": "test-api-key",
            "chunk_size": 1000,
            "max_retries": 3,
            "show_progress_bar": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for version-specific files."""

    async def test_update_build_config_openai(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "model": {"options": [], "value": ""},
            "api_key": {"display_name": "API Key", "required": True, "show": True},
            "api_base": {"display_name": "API Base URL", "value": ""},
            "project_id": {"show": False},
        }
        updated_config = component.update_build_config(build_config, "OpenAI", "provider")
        assert updated_config["model"]["options"] == OPENAI_EMBEDDING_MODEL_NAMES
        assert updated_config["model"]["value"] == OPENAI_EMBEDDING_MODEL_NAMES[0]
        assert updated_config["api_key"]["display_name"] == "OpenAI API Key"
        assert updated_config["api_key"]["required"] is True
        assert updated_config["api_key"]["show"] is True
        assert updated_config["api_base"]["display_name"] == "OpenAI API Base URL"
        assert updated_config["project_id"]["show"] is False

    async def test_update_build_config_ollama(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "model": {"options": [], "value": ""},
            "api_key": {"display_name": "API Key", "required": True, "show": True},
            "api_base": {"display_name": "API Base URL", "value": ""},
            "project_id": {"show": False},
        }
        updated_config = component.update_build_config(build_config, "Ollama", "provider")
        assert updated_config["model"]["options"] == OLLAMA_EMBEDDING_MODELS
        assert updated_config["model"]["value"] == OLLAMA_EMBEDDING_MODELS[0]
        assert updated_config["api_key"]["display_name"] == "API Key (Optional)"
        assert updated_config["api_key"]["required"] is False
        assert updated_config["api_key"]["show"] is False
        assert updated_config["api_base"]["display_name"] == "Ollama Base URL"
        assert updated_config["api_base"]["value"] == "http://localhost:11434"
        assert updated_config["project_id"]["show"] is False

    async def test_update_build_config_watsonx(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "model": {"options": [], "value": ""},
            "api_key": {"display_name": "API Key", "required": True, "show": True},
            "api_base": {"display_name": "API Base URL", "value": ""},
            "project_id": {"show": False},
        }
        updated_config = component.update_build_config(build_config, "IBM watsonx.ai", "provider")
        assert updated_config["model"]["options"] == WATSONX_EMBEDDING_MODEL_NAMES
        assert updated_config["model"]["value"] == WATSONX_EMBEDDING_MODEL_NAMES[0]
        assert updated_config["api_key"]["display_name"] == "IBM watsonx.ai API Key"
        assert updated_config["api_key"]["required"] is True
        assert updated_config["api_key"]["show"] is True
        assert updated_config["api_base"]["display_name"] == "IBM watsonx.ai URL"
        assert updated_config["api_base"]["value"] == "https://us-south.ml.cloud.ibm.com"
        assert updated_config["project_id"]["show"] is True

    @patch("lfx.components.models.embedding_model.OpenAIEmbeddings")
    async def test_build_embeddings_openai(self, mock_openai_embeddings, component_class, default_kwargs):
        # Setup mock
        mock_instance = MagicMock()
        mock_openai_embeddings.return_value = mock_instance

        # Create and configure the component
        component = component_class(**default_kwargs)
        component.provider = "OpenAI"
        component.model = "text-embedding-3-small"
        component.api_key = "test-key"
        component.chunk_size = 1000
        component.max_retries = 3
        component.show_progress_bar = False

        # Build the embeddings
        embeddings = component.build_embeddings()

        # Verify the OpenAIEmbeddings was called with the correct parameters
        mock_openai_embeddings.assert_called_once_with(
            model="text-embedding-3-small",
            dimensions=None,
            base_url=None,
            api_key="test-key",
            chunk_size=1000,
            max_retries=3,
            timeout=None,
            show_progress_bar=False,
            model_kwargs={},
        )
        assert embeddings == mock_instance

    @patch("langchain_ollama.OllamaEmbeddings")
    async def test_build_embeddings_ollama(self, mock_ollama_embeddings, component_class, default_kwargs):
        # Setup mock
        mock_instance = MagicMock()
        mock_ollama_embeddings.return_value = mock_instance

        # Create and configure the component
        kwargs = default_kwargs.copy()
        kwargs["provider"] = "Ollama"
        kwargs["model"] = "nomic-embed-text"
        component = component_class(**kwargs)
        component.api_base = "http://localhost:11434"

        # Build the embeddings
        embeddings = component.build_embeddings()

        # Verify the OllamaEmbeddings was called with the correct parameters
        mock_ollama_embeddings.assert_called_once_with(
            model="nomic-embed-text",
            base_url="http://localhost:11434",
        )
        assert embeddings == mock_instance

    @patch("langchain_ibm.WatsonxEmbeddings")
    async def test_build_embeddings_watsonx(self, mock_watsonx_embeddings, component_class, default_kwargs):
        # Setup mock
        mock_instance = MagicMock()
        mock_watsonx_embeddings.return_value = mock_instance

        # Create and configure the component
        kwargs = default_kwargs.copy()
        kwargs["provider"] = "IBM watsonx.ai"
        kwargs["model"] = "ibm/granite-embedding-125m-english"
        component = component_class(**kwargs)
        component.project_id = "test-project-id"

        # Build the embeddings
        embeddings = component.build_embeddings()

        # Verify the WatsonxEmbeddings was called with the correct parameters
        mock_watsonx_embeddings.assert_called_once_with(
            model_id="ibm/granite-embedding-125m-english",
            url="https://us-south.ml.cloud.ibm.com",
            apikey="test-api-key",
            project_id="test-project-id",
        )
        assert embeddings == mock_instance

    async def test_build_embeddings_watsonx_missing_project_id(self, component_class, default_kwargs):
        kwargs = default_kwargs.copy()
        kwargs["provider"] = "IBM watsonx.ai"
        component = component_class(**kwargs)
        component.project_id = None

        with pytest.raises(ValueError, match=r"Project ID is required for IBM watsonx.ai"):
            component.build_embeddings()

    async def test_build_embeddings_openai_missing_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.provider = "OpenAI"
        component.api_key = None

        with pytest.raises(ValueError, match="OpenAI API key is required when using OpenAI provider"):
            component.build_embeddings()

    async def test_build_embeddings_watsonx_missing_api_key(self, component_class, default_kwargs):
        kwargs = default_kwargs.copy()
        kwargs["provider"] = "IBM watsonx.ai"
        kwargs["api_key"] = None
        component = component_class(**kwargs)
        component.api_key = None
        component.project_id = "test-project"

        with pytest.raises(ValueError, match=r"IBM watsonx.ai API key is required when using IBM watsonx.ai provider"):
            component.build_embeddings()

    async def test_build_embeddings_unknown_provider(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.provider = "Unknown"

        with pytest.raises(ValueError, match="Unknown provider: Unknown"):
            component.build_embeddings()
