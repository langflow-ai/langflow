import pytest

from langflow.components.langchain_utilities import RecursiveCharacterTextSplitterComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestRecursiveCharacterTextSplitterComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return RecursiveCharacterTextSplitterComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "data_input": "This is a sample text that needs to be split into chunks.",
            "separators": ["\\n\\n", "\\n", " ", ""],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "textsplitters", "file_name": "RecursiveCharacterTextSplitter"},
        ]

    async def test_build_text_splitter(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        text_splitter = component.build_text_splitter()
        assert text_splitter is not None
        assert text_splitter.chunk_size == default_kwargs["chunk_size"]
        assert text_splitter.chunk_overlap == default_kwargs["chunk_overlap"]
        assert text_splitter.separators == default_kwargs["separators"]

    async def test_get_data_input(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        data_input = component.get_data_input()
        assert data_input == default_kwargs["data_input"]
