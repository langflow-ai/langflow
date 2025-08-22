from unittest.mock import MagicMock, patch

import pytest
from langflow.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES
from langflow.components.models.embedding_model import EmbeddingModelComponent

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
            "api_key": {"display_name": "API Key"},
            "api_base": {"display_name": "API Base URL"},
        }
        updated_config = component.update_build_config(build_config, "OpenAI", "provider")
        assert updated_config["model"]["options"] == OPENAI_EMBEDDING_MODEL_NAMES
        assert updated_config["model"]["value"] == OPENAI_EMBEDDING_MODEL_NAMES[0]
        assert updated_config["api_key"]["display_name"] == "OpenAI API Key"
        assert updated_config["api_base"]["display_name"] == "OpenAI API Base URL"

    @patch("langflow.components.models.embedding_model.OpenAIEmbeddings")
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

    async def test_build_embeddings_openai_missing_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.provider = "OpenAI"
        component.api_key = None

        with pytest.raises(ValueError, match="OpenAI API key is required when using OpenAI provider"):
            component.build_embeddings()

    async def test_build_embeddings_unknown_provider(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.provider = "Unknown"

        with pytest.raises(ValueError, match="Unknown provider: Unknown"):
            component.build_embeddings()
