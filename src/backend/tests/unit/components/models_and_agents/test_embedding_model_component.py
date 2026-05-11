from unittest.mock import MagicMock, patch

import pytest
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

    @patch("lfx.components.models_and_agents.embedding_model.get_embeddings")
    def test_build_embeddings_openai(self, mock_get_embeddings, component_class, default_kwargs):
        """Test that build_embeddings delegates to get_embeddings with correct kwargs."""
        mock_instance = MagicMock()
        mock_get_embeddings.return_value = mock_instance

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

        result = component.build_embeddings()

        # Verify get_embeddings was called with correct parameters
        mock_get_embeddings.assert_called_once()
        call_kwargs = mock_get_embeddings.call_args.kwargs
        assert call_kwargs["api_key"] == "test-key"
        assert call_kwargs["chunk_size"] == 1000
        assert call_kwargs["max_retries"] == 3
        assert call_kwargs["show_progress_bar"] is False
        assert call_kwargs["model"][0]["name"] == "text-embedding-3-small"
        assert call_kwargs["model"][0]["provider"] == "OpenAI"

        # Result should be whatever get_embeddings returns
        assert result == mock_instance

    @patch("lfx.base.models.unified_models.get_api_key_for_provider")
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

    @patch("lfx.base.models.unified_models.get_api_key_for_provider")
    @patch("lfx.base.models.unified_models.get_embedding_class")
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

    @patch("lfx.components.models_and_agents.embedding_model.get_embeddings")
    def test_build_embeddings_google(self, mock_get_embeddings, component_class):
        """Test that build_embeddings passes correct params for Google provider."""
        mock_instance = MagicMock()
        mock_get_embeddings.return_value = mock_instance

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

        result = component.build_embeddings()

        # Verify get_embeddings was called with correct parameters
        mock_get_embeddings.assert_called_once()
        call_kwargs = mock_get_embeddings.call_args.kwargs
        assert call_kwargs["model"][0]["name"] == "models/text-embedding-004"
        assert call_kwargs["model"][0]["provider"] == "Google Generative AI"
        assert call_kwargs["api_key"] == "test-google-key"

        assert result == mock_instance

    @patch("lfx.components.models_and_agents.embedding_model.get_embeddings")
    def test_build_embeddings_passes_watsonx_params(self, mock_get_embeddings, component_class):
        """Test that watsonx-specific params are forwarded to get_embeddings."""
        mock_get_embeddings.return_value = MagicMock()

        component = component_class(
            model=[
                {
                    "name": "ibm/slate-125m-english-rtrvr",
                    "provider": "IBM WatsonX",
                    "metadata": {
                        "embedding_class": "WatsonxEmbeddings",
                        "param_mapping": {
                            "model_id": "model_id",
                            "api_key": "apikey",
                            "url": "url",
                            "project_id": "project_id",
                        },
                    },
                }
            ],
            api_key="test-watsonx-key",
        )
        component._user_id = "test-user-id"
        component.base_url_ibm_watsonx = "https://us-south.ml.cloud.ibm.com"
        component.project_id = "my-project-id"
        component.api_base = None
        component.dimensions = None
        component.chunk_size = None
        component.request_timeout = None
        component.max_retries = None
        component.show_progress_bar = None
        component.model_kwargs = None

        component.build_embeddings()

        call_kwargs = mock_get_embeddings.call_args.kwargs
        assert call_kwargs["watsonx_url"] == "https://us-south.ml.cloud.ibm.com"
        assert call_kwargs["watsonx_project_id"] == "my-project-id"

    @patch("lfx.components.models_and_agents.embedding_model.get_embeddings")
    def test_build_embeddings_passes_all_optional_params(self, mock_get_embeddings, component_class, default_kwargs):
        """Test that all optional parameters are forwarded correctly."""
        mock_get_embeddings.return_value = MagicMock()

        component = component_class(**default_kwargs)
        component._user_id = "test-user-id"
        component.api_key = "test-key"
        component.api_base = "https://custom.api.base"
        component.dimensions = 512
        component.chunk_size = 500
        component.request_timeout = 30.0
        component.max_retries = 5
        component.show_progress_bar = True
        component.model_kwargs = {"extra_param": "value"}

        component.build_embeddings()

        call_kwargs = mock_get_embeddings.call_args.kwargs
        assert call_kwargs["api_base"] == "https://custom.api.base"
        assert call_kwargs["dimensions"] == 512
        assert call_kwargs["chunk_size"] == 500
        assert call_kwargs["request_timeout"] == 30.0
        assert call_kwargs["max_retries"] == 5
        assert call_kwargs["show_progress_bar"] is True
        assert call_kwargs["model_kwargs"] == {"extra_param": "value"}
