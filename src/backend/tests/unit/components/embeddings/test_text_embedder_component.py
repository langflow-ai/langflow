from unittest.mock import Mock

import pytest

from langflow.components.embeddings import TextEmbedderComponent
from langflow.schema import Data
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestTextEmbedderComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return TextEmbedderComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "embedding_model": Mock(embed_documents=Mock(return_value=[[0.1, 0.2, 0.3]])),
            "message": Mock(text="Sample text for embedding"),
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_generate_embeddings_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.generate_embeddings()

        assert isinstance(result, Data)
        assert result.data["text"] == "Sample text for embedding"
        assert result.data["embeddings"] == [0.1, 0.2, 0.3]
        assert "error" not in result.data

    def test_generate_embeddings_invalid_model(self, component_class):
        component = component_class(embedding_model=None, message=Mock(text="Sample text"))

        result = component.generate_embeddings()

        assert isinstance(result, Data)
        assert result.data["text"] == ""
        assert result.data["embeddings"] == []
        assert "Invalid or incompatible embedding model" in result.data["error"]

    def test_generate_embeddings_no_text(self, component_class):
        component = component_class(
            embedding_model=Mock(embed_documents=Mock(return_value=[[0.1, 0.2, 0.3]])), message=Mock(text="")
        )

        result = component.generate_embeddings()

        assert isinstance(result, Data)
        assert result.data["text"] == ""
        assert result.data["embeddings"] == []
        assert "No text content found in message" in result.data["error"]

    def test_generate_embeddings_invalid_output(self, component_class):
        component = component_class(
            embedding_model=Mock(embed_documents=Mock(return_value=None)), message=Mock(text="Sample text")
        )

        result = component.generate_embeddings()

        assert isinstance(result, Data)
        assert result.data["text"] == "Sample text"
        assert result.data["embeddings"] == []
        assert "Invalid embeddings generated" in result.data["error"]
