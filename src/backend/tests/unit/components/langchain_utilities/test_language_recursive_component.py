import pytest
from langflow.components.langchain_utilities import LanguageRecursiveTextSplitterComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestLanguageRecursiveTextSplitterComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return LanguageRecursiveTextSplitterComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "data_input": ["This is a sample text that needs to be split into chunks."],
            "code_language": "python",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "textsplitters", "file_name": "LanguageRecursiveTextSplitter"},
        ]

    async def test_build_text_splitter(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        text_splitter = component.build_text_splitter()
        assert text_splitter is not None
        assert isinstance(text_splitter, RecursiveCharacterTextSplitter)

    async def test_get_data_input(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        data_input = component.get_data_input()
        assert data_input == default_kwargs["data_input"]

    async def test_text_splitter_functionality(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        text_splitter = component.build_text_splitter()
        chunks = text_splitter.split_text(default_kwargs["data_input"][0])
        assert len(chunks) > 0
        assert all(len(chunk) <= default_kwargs["chunk_size"] for chunk in chunks)
