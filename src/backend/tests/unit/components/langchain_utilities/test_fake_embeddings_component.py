import pytest

from langflow.components.langchain_utilities import FakeEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestFakeEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return FakeEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"dimensions": 5}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_embeddings(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        embeddings = component.build_embeddings()

        # Assert
        assert embeddings is not None
        assert hasattr(embeddings, "embed")  # Check if the embeddings object has the 'embed' method
        assert len(embeddings.embed("test")) == default_kwargs["dimensions"]  # Validate dimensions

    def test_default_dimensions(self, component_class):
        # Arrange
        component = component_class()

        # Act
        embeddings = component.build_embeddings()

        # Assert
        assert embeddings is not None
        assert len(embeddings.embed("test")) == 5  # Validate default dimensions
