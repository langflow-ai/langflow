from unittest.mock import MagicMock, patch

import pytest
from lfx.components.gigachat.gigachat_embeddings import GigaChatEmbeddingsComponent

from tests.base import ComponentTestBaseWithoutClient


class TestGigaChatEmbeddingsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return GigaChatEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"model": "EmbeddingsGigaR", "scope": "GIGACHAT_API_PERS", "credentials": "test-api-key"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_gigachat_initialization(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        assert component.display_name == "GigaChat Embeddings"
        assert component.description == "Generate embeddings using GigaChat models."
        assert component.icon == "GigaChat"

    @patch("lfx.components.gigachat.gigachat_embeddings.GigaChatEmbeddings")
    def test_build_embeddings(self, mock_embeddings, component_class, default_kwargs):
        mock_instance = MagicMock()
        mock_embeddings.return_value = mock_instance

        component = component_class(**default_kwargs)
        embeddings = component.build_embeddings()

        mock_embeddings.assert_called_once_with(
            base_url=None,
            auth_url=None,
            credentials="test-api-key",
            scope="GIGACHAT_API_PERS",
            model="EmbeddingsGigaR",
            user=None,
            password=None,
            timeout=700,
            verify_ssl_certs=False,
        )
        assert embeddings == mock_instance
