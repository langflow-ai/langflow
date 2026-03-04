from unittest.mock import MagicMock, patch

import pytest
from lfx.base.embeddings.embeddings_class import EmbeddingsWithModels
from lfx.components.models_and_agents import EmbeddingModelComponent

from tests.base import ComponentTestBaseWithoutClient


class TestEmbeddingModelComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return EmbeddingModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model": [
                {
                    "name": "text-embedding-3-small",
                    "provider": "OpenAI",
                    "metadata": {
                        "embedding_class": "OpenAIEmbeddings",
                        "param_mapping": {
                            "model": "model",
                            "api_key": "api_key",
                            "api_base": "base_url",
                            "dimensions": "dimensions",
                            "chunk_size": "chunk_size",
                            "request_timeout": "request_timeout",
                            "max_retries": "max_retries",
                            "show_progress_bar": "show_progress_bar",
                            "model_kwargs": "model_kwargs",
                        },
                    },
                }
            ],
            "api_key": "test-api-key",
            "chunk_size": 1000,
            "max_retries": 3,
            "show_progress_bar": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for version-specific files."""
        return []

    @patch("lfx.components.models_and_agents.embedding_model.get_unified_models_detailed")
    @patch("lfx.components.models_and_agents.embedding_model.get_api_key_for_provider")
    @patch("lfx.components.models_and_agents.embedding_model.get_embedding_class")
    @patch("lfx.components.models_and_agents.embedding_model.get_embeddings")
    def test_build_embeddings_openai(
        self,
        mock_get_embeddings,
        mock_get_embedding_class,
        mock_get_api_key,
        mock_get_unified_models,
        component_class,
        default_kwargs,
    ):
        # Setup mock for get_api_key_for_provider
        mock_get_api_key.return_value = "test-key"
        # Setup mock for get_unified_models_detailed to return empty (no available models)
        mock_get_unified_models.return_value = []
        # Setup mock for get_embeddings (primary instance creation)
        mock_instance = MagicMock()
        mock_get_embeddings.return_value = mock_instance
        # Setup mock for get_embedding_class (used in _build_available_models)
        mock_openai_class = MagicMock()
        mock_get_embedding_class.return_value = mock_openai_class

        # Create and configure the component
        component = component_class(**default_kwargs)
        component._user_id = "test-user-id"
        component.api_key = "test-key"
        component.chunk_size = 1000
        component.max_retries = 3
        component.show_progress_bar = False
        component.api_base = None
        component.dimensions = None
        component.request_timeout = None
        component.model_kwargs = None

        # Build the embeddings
        embeddings = component.build_embeddings()

        # Verify get_embeddings was called with correct parameters
        mock_get_embeddings.assert_called_once()
        call_kwargs = mock_get_embeddings.call_args.kwargs
        assert call_kwargs["api_key"] == "test-key"
        assert call_kwargs["chunk_size"] == 1000
        assert call_kwargs["max_retries"] == 3
        assert call_kwargs["show_progress_bar"] is False
        assert call_kwargs["model"][0]["name"] == "text-embedding-3-small"
        assert call_kwargs["model"][0]["provider"] == "OpenAI"

        # Verify the embedding class getter was called for _build_available_models
        mock_get_embedding_class.assert_called_once_with("OpenAIEmbeddings")

        # Verify the result is wrapped in EmbeddingsWithModels
        assert isinstance(embeddings, EmbeddingsWithModels)
        assert embeddings.embeddings == mock_instance
        assert embeddings.available_models == {}

    @patch("lfx.components.models_and_agents.embedding_model.get_api_key_for_provider")
    def test_build_embeddings_openai_missing_api_key(self, mock_get_api_key, component_class, default_kwargs):
        # Setup mock to return None (no API key)
        mock_get_api_key.return_value = None

        component = component_class(**default_kwargs)
        component._user_id = "test-user-id"
        component.api_key = None

        with pytest.raises(ValueError, match="OpenAI API key is required"):
            component.build_embeddings()

    def test_build_embeddings_invalid_model_format(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.model = None

        with pytest.raises(ValueError, match="An embedding model selection is required"):
            component.build_embeddings()

    @patch("lfx.components.models_and_agents.embedding_model.get_api_key_for_provider")
    @patch("lfx.components.models_and_agents.embedding_model.get_embedding_class")
    def test_build_embeddings_unknown_embedding_class(
        self, mock_get_embedding_class, mock_get_api_key, component_class, default_kwargs
    ):
        # Setup mock for get_api_key_for_provider
        mock_get_api_key.return_value = "test-key"
        # Setup mock to raise ValueError for unknown class
        mock_get_embedding_class.side_effect = ValueError("Unknown embedding class: UnknownEmbeddingClass")

        component = component_class(**default_kwargs)
        component._user_id = "test-user-id"
        component.model = [
            {
                "name": "unknown-model",
                "provider": "Unknown",
                "metadata": {
                    "embedding_class": "UnknownEmbeddingClass",
                    "param_mapping": {},
                },
            }
        ]

        with pytest.raises(ValueError, match="Unknown embedding class: UnknownEmbeddingClass"):
            component.build_embeddings()

    @patch("lfx.components.models_and_agents.embedding_model.get_unified_models_detailed")
    @patch("lfx.components.models_and_agents.embedding_model.get_api_key_for_provider")
    @patch("lfx.components.models_and_agents.embedding_model.get_embedding_class")
    @patch("lfx.components.models_and_agents.embedding_model.get_embeddings")
    def test_build_embeddings_google(
        self,
        mock_get_embeddings,
        mock_get_embedding_class,
        mock_get_api_key,
        mock_get_unified_models,
        component_class,
    ):
        # Setup mock for get_api_key_for_provider
        mock_get_api_key.return_value = "test-google-key"
        # Setup mock for get_unified_models_detailed to return empty (no available models)
        mock_get_unified_models.return_value = []
        # Setup mock for get_embeddings (primary instance creation)
        mock_instance = MagicMock()
        mock_get_embeddings.return_value = mock_instance
        # Setup mock for get_embedding_class (used in _build_available_models)
        mock_google_class = MagicMock()
        mock_get_embedding_class.return_value = mock_google_class

        # Create component with Google Generative AI configuration
        component = component_class(
            model=[
                {
                    "name": "models/text-embedding-004",
                    "provider": "Google Generative AI",
                    "metadata": {
                        "embedding_class": "GoogleGenerativeAIEmbeddings",
                        "param_mapping": {
                            "model": "model",
                            "api_key": "google_api_key",
                            "request_timeout": "request_options",
                            "model_kwargs": "client_options",
                        },
                    },
                }
            ],
            api_key="test-google-key",
        )
        component._user_id = "test-user-id"
        component.api_base = None
        component.dimensions = None
        component.chunk_size = None
        component.request_timeout = None
        component.max_retries = None
        component.show_progress_bar = None
        component.model_kwargs = None

        # Build the embeddings
        embeddings = component.build_embeddings()

        # Verify get_embeddings was called with correct parameters
        mock_get_embeddings.assert_called_once()
        call_kwargs = mock_get_embeddings.call_args.kwargs
        assert call_kwargs["model"][0]["name"] == "models/text-embedding-004"
        assert call_kwargs["model"][0]["provider"] == "Google Generative AI"
        assert call_kwargs["api_key"] == "test-google-key"

        # Verify the embedding class getter was called for _build_available_models
        mock_get_embedding_class.assert_called_once_with("GoogleGenerativeAIEmbeddings")

        # Verify the result is wrapped in EmbeddingsWithModels
        assert isinstance(embeddings, EmbeddingsWithModels)
        assert embeddings.embeddings == mock_instance
        assert embeddings.available_models == {}

    @patch("lfx.components.models_and_agents.embedding_model.get_unified_models_detailed")
    @patch("lfx.components.models_and_agents.embedding_model.get_api_key_for_provider")
    @patch("lfx.components.models_and_agents.embedding_model.get_embedding_class")
    def test_build_embeddings_with_available_models(
        self, mock_get_embedding_class, mock_get_api_key, mock_get_unified_models, component_class, default_kwargs
    ):
        """Test that available_models dict is populated from unified models."""
        # Setup mock for get_api_key_for_provider
        mock_get_api_key.return_value = "test-key"

        # Setup mock for get_unified_models_detailed to return multiple models
        mock_get_unified_models.return_value = [
            {
                "provider": "OpenAI",
                "models": [
                    {"model_name": "text-embedding-3-small"},
                    {"model_name": "text-embedding-3-large"},
                    {"model_name": "text-embedding-ada-002"},
                ],
            }
        ]

        # Setup mock for embedding classes
        mock_openai_class = MagicMock()
        # Create different mock instances for each model
        mock_instances = {
            "text-embedding-3-small": MagicMock(name="small"),
            "text-embedding-3-large": MagicMock(name="large"),
            "text-embedding-ada-002": MagicMock(name="ada"),
        }
        mock_openai_class.side_effect = lambda **kwargs: mock_instances.get(kwargs.get("model"), MagicMock())
        mock_get_embedding_class.return_value = mock_openai_class

        # Create and configure the component
        component = component_class(**default_kwargs)
        component._user_id = "test-user-id"
        component.api_key = "test-key"
        component.chunk_size = 1000
        component.max_retries = 3
        component.show_progress_bar = False
        component.api_base = None
        component.dimensions = None
        component.request_timeout = None
        component.model_kwargs = None

        # Build the embeddings
        embeddings = component.build_embeddings()

        # Verify the result is wrapped in EmbeddingsWithModels
        assert isinstance(embeddings, EmbeddingsWithModels)

        # Verify available_models contains all models from unified models
        assert "text-embedding-3-small" in embeddings.available_models
        assert "text-embedding-3-large" in embeddings.available_models
        assert "text-embedding-ada-002" in embeddings.available_models
        assert len(embeddings.available_models) == 3
