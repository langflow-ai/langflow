import pytest

from langflow.components.vectorstores import VectaraSelfQueryRetriverComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestVectaraSelfQueryRetriverComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return VectaraSelfQueryRetriverComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "vectorstore": "mock_vector_store",
            "document_content_description": "Description of the document content.",
            "llm": "mock_language_model",
            "metadata_field_info": [
                '{"name":"field1","description":"Description of field1","type":"string"}',
                '{"name":"field2","description":"Description of field2","type":"list[string]"}',
            ],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectara", "file_name": "VectaraSelfQueryRetriever"},
        ]

    def test_build_retriever(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        retriever = component.build(
            vectorstore=default_kwargs["vectorstore"],
            document_content_description=default_kwargs["document_content_description"],
            llm=default_kwargs["llm"],
            metadata_field_info=default_kwargs["metadata_field_info"],
        )

        # Assert
        assert retriever is not None
        assert isinstance(retriever, SelfQueryRetriever)

    def test_invalid_metadata_field_info(self, component_class, default_kwargs):
        # Arrange
        default_kwargs["metadata_field_info"] = [
            '{"name":"field1","description":"Description of field1"}'
        ]  # Missing type
        component = component_class(**default_kwargs)

        # Act & Assert
        with pytest.raises(ValueError, match="Incorrect metadata field info format."):
            component.build(
                vectorstore=default_kwargs["vectorstore"],
                document_content_description=default_kwargs["document_content_description"],
                llm=default_kwargs["llm"],
                metadata_field_info=default_kwargs["metadata_field_info"],
            )
