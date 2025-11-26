from unittest.mock import MagicMock, patch

import pytest
from lfx.base.embeddings.embeddings_class import EmbeddingsWithModels
from lfx.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES
from lfx.base.models.watsonx_constants import WATSONX_EMBEDDING_MODEL_NAMES
from lfx.components.models_and_agents.embedding_model import EmbeddingModelComponent

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
            "api_key": "test-api-key",  # pragma:allowlist secret
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
            "api_base": {"display_name": "API Base URL", "value": "", "advanced": False, "show": False},
            "base_url_ibm_watsonx": {"show": False},
            "project_id": {"show": False},
            "ollama_base_url": {"show": False},
            "truncate_input_tokens": {"show": False},
            "input_text": {"show": False},
        }
        updated_config = await component.update_build_config(build_config, "OpenAI", "provider")
        assert updated_config["model"]["options"] == OPENAI_EMBEDDING_MODEL_NAMES
        assert updated_config["model"]["value"] == OPENAI_EMBEDDING_MODEL_NAMES[0]
        assert updated_config["api_key"]["display_name"] == "OpenAI API Key"
        assert updated_config["api_key"]["required"] is True
        assert updated_config["api_key"]["show"] is True
        assert updated_config["api_base"]["display_name"] == "OpenAI API Base URL"
        assert updated_config["api_base"]["advanced"] is True
        assert updated_config["api_base"]["show"] is True
        assert updated_config["project_id"]["show"] is False
        assert updated_config["base_url_ibm_watsonx"]["show"] is False
        assert updated_config["ollama_base_url"]["show"] is False
        assert updated_config["truncate_input_tokens"]["show"] is False
        assert updated_config["input_text"]["show"] is False

    @patch("lfx.components.models_and_agents.embedding_model.get_ollama_models")
    @patch("lfx.components.models_and_agents.embedding_model.is_valid_ollama_url")
    async def test_update_build_config_ollama(
        self, mock_is_valid_url, mock_get_ollama_models, component_class, default_kwargs
    ):
        # Mock the validation and model fetching
        mock_is_valid_url.return_value = True
        mock_get_ollama_models.return_value = ["nomic-embed-text", "mxbai-embed-large"]

        component = component_class(**default_kwargs)
        component.ollama_base_url = "http://localhost:11434"
        build_config = {
            "model": {"options": [], "value": ""},
            "api_key": {"display_name": "API Key", "required": True, "show": True},
            "api_base": {"display_name": "API Base URL", "value": "", "show": False},
            "project_id": {"show": False},
            "base_url_ibm_watsonx": {"show": False},
            "ollama_base_url": {"show": False},
            "truncate_input_tokens": {"show": False},
            "input_text": {"show": False},
        }
        updated_config = await component.update_build_config(build_config, "Ollama", "provider")
        assert updated_config["model"]["options"] == ["nomic-embed-text", "mxbai-embed-large"]
        assert updated_config["model"]["value"] == "nomic-embed-text"
        assert updated_config["api_key"]["display_name"] == "API Key (Optional)"
        assert updated_config["api_key"]["required"] is False
        assert updated_config["api_key"]["show"] is False
        assert updated_config["api_base"]["show"] is False
        assert updated_config["project_id"]["show"] is False
        assert updated_config["base_url_ibm_watsonx"]["show"] is False
        assert updated_config["ollama_base_url"]["show"] is True
        assert updated_config["truncate_input_tokens"]["show"] is False
        assert updated_config["input_text"]["show"] is False

    @patch.object(EmbeddingModelComponent, "fetch_ibm_models")
    async def test_update_build_config_watsonx(self, mock_fetch_ibm_models, component_class, default_kwargs):
        mock_fetch_ibm_models.return_value = WATSONX_EMBEDDING_MODEL_NAMES

        component = component_class(**default_kwargs)
        build_config = {
            "model": {"options": [], "value": ""},
            "api_key": {"display_name": "API Key", "required": True, "show": True},
            "api_base": {"display_name": "API Base URL", "value": "", "show": False},
            "project_id": {"show": False},
            "base_url_ibm_watsonx": {"show": False},
            "ollama_base_url": {"show": False},
            "truncate_input_tokens": {"show": False},
            "input_text": {"show": False},
        }
        updated_config = await component.update_build_config(build_config, "IBM watsonx.ai", "provider")
        assert updated_config["model"]["options"] == WATSONX_EMBEDDING_MODEL_NAMES
        assert updated_config["model"]["value"] == WATSONX_EMBEDDING_MODEL_NAMES[0]
        assert updated_config["api_key"]["display_name"] == "IBM watsonx.ai API Key"
        assert updated_config["api_key"]["required"] is True
        assert updated_config["api_key"]["show"] is True
        assert updated_config["api_base"]["show"] is False
        assert updated_config["base_url_ibm_watsonx"]["show"] is True
        assert updated_config["project_id"]["show"] is True
        assert updated_config["ollama_base_url"]["show"] is False
        assert updated_config["truncate_input_tokens"]["show"] is True
        assert updated_config["input_text"]["show"] is True

    @patch("lfx.components.models_and_agents.embedding_model.OpenAIEmbeddings")
    async def test_build_embeddings_openai(self, mock_openai_embeddings, component_class, default_kwargs):
        # Setup mock
        mock_instance = MagicMock()
        mock_openai_embeddings.return_value = mock_instance

        # Create and configure the component
        component = component_class(**default_kwargs)
        component.provider = "OpenAI"
        component.model = "text-embedding-3-small"
        component.api_key = "test-key"  # pragma:allowlist secret
        component.chunk_size = 1000
        component.max_retries = 3
        component.show_progress_bar = False

        # Build the embeddings
        embeddings = await component.build_embeddings()

        # Verify the result is EmbeddingsWithModels
        assert isinstance(embeddings, EmbeddingsWithModels)

        # Verify OpenAIEmbeddings was called multiple times (primary + once per available model)
        # Primary instance + one per model name = 1 + len(OPENAI_EMBEDDING_MODEL_NAMES)
        assert mock_openai_embeddings.call_count == 1 + len(OPENAI_EMBEDDING_MODEL_NAMES)

        # Verify available_models dict is populated
        assert isinstance(embeddings.available_models, dict)
        assert len(embeddings.available_models) == len(OPENAI_EMBEDDING_MODEL_NAMES)
        assert "text-embedding-3-small" in embeddings.available_models

    @patch("lfx.components.models_and_agents.embedding_model.get_ollama_models")
    @patch("langchain_ollama.OllamaEmbeddings")
    async def test_build_embeddings_ollama(
        self, mock_ollama_embeddings, mock_get_ollama_models, component_class, default_kwargs
    ):
        # Setup mocks
        mock_instance = MagicMock()
        mock_ollama_embeddings.return_value = mock_instance
        mock_get_ollama_models.return_value = ["nomic-embed-text", "mxbai-embed-large"]

        # Create and configure the component
        kwargs = default_kwargs.copy()
        kwargs["provider"] = "Ollama"
        kwargs["model"] = "nomic-embed-text"
        kwargs["model_kwargs"] = {}
        component = component_class(**kwargs)
        component.ollama_base_url = "http://localhost:11434"

        # Build the embeddings
        embeddings = await component.build_embeddings()

        # Verify the result is EmbeddingsWithModels
        assert isinstance(embeddings, EmbeddingsWithModels)

        # Verify OllamaEmbeddings was called multiple times (primary + once per available model)
        # Primary instance + one per model returned by get_ollama_models
        assert mock_ollama_embeddings.call_count == 1 + 2  # 1 primary + 2 from get_ollama_models

        # Verify available_models dict is populated
        assert isinstance(embeddings.available_models, dict)
        assert len(embeddings.available_models) == 2
        assert "nomic-embed-text" in embeddings.available_models

    @patch.object(EmbeddingModelComponent, "fetch_ibm_models")
    @patch("ibm_watsonx_ai.APIClient")
    @patch("ibm_watsonx_ai.Credentials")
    @patch("langchain_ibm.WatsonxEmbeddings")
    async def test_build_embeddings_watsonx(
        self,
        mock_watsonx_embeddings,
        mock_credentials,
        mock_api_client,
        mock_fetch_ibm_models,
        component_class,
        default_kwargs,
    ):
        # Setup mocks
        mock_instance = MagicMock()
        mock_watsonx_embeddings.return_value = mock_instance
        mock_cred_instance = MagicMock()
        mock_credentials.return_value = mock_cred_instance
        mock_client_instance = MagicMock()
        mock_api_client.return_value = mock_client_instance
        mock_fetch_ibm_models.return_value = WATSONX_EMBEDDING_MODEL_NAMES

        # Create and configure the component
        kwargs = default_kwargs.copy()
        kwargs["provider"] = "IBM watsonx.ai"
        kwargs["model"] = "ibm/granite-embedding-125m-english"
        component = component_class(**kwargs)
        component.project_id = "test-project-id"
        component.truncate_input_tokens = 200
        component.input_text = True

        # Build the embeddings
        embeddings = await component.build_embeddings()

        # Verify the result is EmbeddingsWithModels
        assert isinstance(embeddings, EmbeddingsWithModels)

        # Verify Credentials was created once (shared across all embeddings)
        assert mock_credentials.call_count == 1

        # Verify APIClient was created once (shared across all embeddings)
        assert mock_api_client.call_count == 1

        # Verify WatsonxEmbeddings was called multiple times (primary + once per available model)
        assert mock_watsonx_embeddings.call_count == 1 + len(WATSONX_EMBEDDING_MODEL_NAMES)

        # Verify available_models dict is populated
        assert isinstance(embeddings.available_models, dict)
        assert len(embeddings.available_models) == len(WATSONX_EMBEDDING_MODEL_NAMES)

    async def test_build_embeddings_watsonx_missing_project_id(self, component_class, default_kwargs):
        kwargs = default_kwargs.copy()
        kwargs["provider"] = "IBM watsonx.ai"
        kwargs["model"] = "ibm/granite-embedding-125m-english"
        component = component_class(**kwargs)
        component.project_id = None

        with pytest.raises(ValueError, match=r"Project ID is required for IBM watsonx.ai"):
            await component.build_embeddings()

    async def test_build_embeddings_openai_missing_api_key(self, component_class, default_kwargs):
        kwargs = default_kwargs.copy()
        kwargs["api_key"] = None
        component = component_class(**kwargs)
        component.provider = "OpenAI"
        component.api_key = None

        with pytest.raises(ValueError, match="OpenAI API key is required when using OpenAI provider"):
            await component.build_embeddings()

    async def test_build_embeddings_watsonx_missing_api_key(self, component_class, default_kwargs):
        kwargs = default_kwargs.copy()
        kwargs["provider"] = "IBM watsonx.ai"
        kwargs["api_key"] = None
        kwargs["model"] = "ibm/granite-embedding-125m-english"
        component = component_class(**kwargs)
        component.api_key = None
        component.project_id = "test-project"

        with pytest.raises(ValueError, match=r"IBM watsonx.ai API key is required when using IBM watsonx.ai provider"):
            await component.build_embeddings()

    async def test_build_embeddings_unknown_provider(self, component_class, default_kwargs):
        kwargs = default_kwargs.copy()
        kwargs["provider"] = "Unknown"
        component = component_class(**kwargs)
        component.provider = "Unknown"

        with pytest.raises(ValueError, match="Unknown provider: Unknown"):
            await component.build_embeddings()
