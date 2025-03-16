import pytest
from langflow.components.langchain_utilities import NaturalLanguageTextSplitterComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestNaturalLanguageTextSplitterComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NaturalLanguageTextSplitterComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "data_input": "This is a sample text for testing the Natural Language Text Splitter.",
            "separator": "\n\n",
            "language": "English",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "textsplitters", "file_name": "NaturalLanguageTextSplitter"},
        ]

    async def test_build_text_splitter(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        text_splitter = component.build_text_splitter()

        # Assert
        assert text_splitter is not None
        assert text_splitter.chunk_size == default_kwargs["chunk_size"]
        assert text_splitter.chunk_overlap == default_kwargs["chunk_overlap"]
        assert text_splitter.language == default_kwargs["language"].lower()
        assert text_splitter.separator == default_kwargs["separator"]

    async def test_get_data_input(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        data_input = component.get_data_input()

        # Assert
        assert data_input == default_kwargs["data_input"]
