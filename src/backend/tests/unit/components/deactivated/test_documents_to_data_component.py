import pytest
from langchain_core.documents import Document

from langflow.components.deactivated.documents_to_data import DocumentsToDataComponent
from langflow.schema import Data
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestDocumentsToDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return DocumentsToDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @pytest.fixture
    def sample_documents(self):
        return [Document(page_content="Sample content 1"), Document(page_content="Sample content 2")]

    def test_build_with_multiple_documents(self, component_class, sample_documents):
        # Arrange
        component = component_class()

        # Act
        result = component.build(sample_documents)

        # Assert
        assert len(result) == len(sample_documents)
        assert all(isinstance(data, Data) for data in result)
        assert all(data.page_content == doc.page_content for data, doc in zip(result, sample_documents, strict=False))

    def test_build_with_single_document(self, component_class):
        # Arrange
        component = component_class()
        single_document = Document(page_content="Single sample content")

        # Act
        result = component.build(single_document)

        # Assert
        assert len(result) == 1
        assert isinstance(result[0], Data)
        assert result[0].page_content == single_document.page_content

    def test_build_with_empty_documents(self, component_class):
        # Arrange
        component = component_class()

        # Act
        result = component.build([])

        # Assert
        assert result == []
