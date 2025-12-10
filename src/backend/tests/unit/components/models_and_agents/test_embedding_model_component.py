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

    @patch("lfx.components.models_and_agents.embedding_model.get_api_key_for_provider")
    @patch("lfx.components.models_and_agents.embedding_model.get_embedding_classes")
    def test_build_embeddings_openai(
        self, mock_get_embedding_classes, mock_get_api_key, component_class, default_kwargs
    ):
        # Setup mock for get_api_key_for_provider
        mock_get_api_key.return_value = "test-key"
        # Setup mock
        mock_openai_class = MagicMock()
        mock_instance = MagicMock()
        mock_openai_class.return_value = mock_instance
        mock_embedding_classes_dict = MagicMock()
        mock_embedding_classes_dict.get.return_value = mock_openai_class
        mock_get_embedding_classes.return_value = mock_embedding_classes_dict

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

        # Verify the embedding class getter was called
        mock_embedding_classes_dict.get.assert_called_once_with("OpenAIEmbeddings")

        # Verify the OpenAIEmbeddings was called with the correct parameters
        mock_openai_class.assert_called_once_with(
            model="text-embedding-3-small",
            api_key="test-key",
            chunk_size=1000,
            max_retries=3,
            show_progress_bar=False,
        )
        assert embeddings == mock_instance

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

        with pytest.raises(ValueError, match="Model must be a non-empty list"):
            component.build_embeddings()

    @patch("lfx.components.models_and_agents.embedding_model.get_api_key_for_provider")
    @patch("lfx.components.models_and_agents.embedding_model.get_embedding_classes")
    def test_build_embeddings_unknown_embedding_class(
        self, mock_get_embedding_classes, mock_get_api_key, component_class, default_kwargs
    ):
        # Setup mock for get_api_key_for_provider
        mock_get_api_key.return_value = "test-key"
        # Setup mock to return None for unknown class
        mock_embedding_classes_dict = MagicMock()
        mock_embedding_classes_dict.get.return_value = None
        mock_get_embedding_classes.return_value = mock_embedding_classes_dict

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

    @patch("lfx.components.models_and_agents.embedding_model.get_api_key_for_provider")
    @patch("lfx.components.models_and_agents.embedding_model.get_embedding_classes")
    def test_build_embeddings_google(self, mock_get_embedding_classes, mock_get_api_key, component_class):
        # Setup mock for get_api_key_for_provider
        mock_get_api_key.return_value = "test-google-key"

        # Setup mock
        mock_google_class = MagicMock()
        mock_instance = MagicMock()
        mock_google_class.return_value = mock_instance
        mock_embedding_classes_dict = MagicMock()
        mock_embedding_classes_dict.get.return_value = mock_google_class
        mock_get_embedding_classes.return_value = mock_embedding_classes_dict

        # Create component with Google configuration
        component = component_class(
            model=[
                {
                    "name": "embedding-001",
                    "provider": "Google",
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

        # Verify the embedding class getter was called
        mock_embedding_classes_dict.get.assert_called_once_with("GoogleGenerativeAIEmbeddings")

        # Verify the GoogleGenerativeAIEmbeddings was called with the correct parameters
        mock_google_class.assert_called_once_with(
            model="embedding-001",
            google_api_key="test-google-key",
        )
        assert embeddings == mock_instance
