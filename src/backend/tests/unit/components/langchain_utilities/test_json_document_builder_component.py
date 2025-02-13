import pytest
from langchain_core.documents import Document

from langflow.components.langchain_utilities import JSONDocumentBuilder
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestJSONDocumentBuilder(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return JSONDocumentBuilder

    @pytest.fixture
    def default_kwargs(self):
        return {}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "utilities", "file_name": "JSONDocumentBuilder"},
        ]

    def test_build_single_document(self, component_class):
        # Arrange
        key = "example_key"
        document = Document(page_content="This is a test document.")
        component = component_class()

        # Act
        result = component.build(key=key, document=document)

        # Assert
        assert isinstance(result, Document)
        assert result.page_content == '{"example_key":"This is a test document."}'

    def test_build_multiple_documents(self, component_class):
        # Arrange
        key = "example_key"
        documents = [Document(page_content="Document 1"), Document(page_content="Document 2")]
        component = component_class()

        # Act
        result = component.build(key=key, document=documents)

        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].page_content == '{"example_key":"Document 1"}'
        assert result[1].page_content == '{"example_key":"Document 2"}'

    def test_build_invalid_document_type(self, component_class):
        # Arrange
        key = "example_key"
        invalid_document = "This is not a Document"
        component = component_class()

        # Act & Assert
        with pytest.raises(TypeError, match="Expected Document or list of Documents, got <class 'str'>"):
            component.build(key=key, document=invalid_document)
