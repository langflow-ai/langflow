import pytest
from langflow.components.tools import WikipediaAPIComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestWikipediaAPIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return WikipediaAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Python programming language",
            "lang": "en",
            "k": 4,
            "load_all_available_meta": False,
            "doc_content_chars_max": 4000,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "wiki", "file_name": "WikipediaAPI"},
        ]

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert isinstance(result, list)
        assert all(isinstance(data, Data) for data in result)

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert isinstance(tool, WikipediaQueryRun)

    async def test_build_wrapper(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        wrapper = component._build_wrapper()
        assert wrapper is not None
        assert wrapper.top_k_results == default_kwargs["k"]
        assert wrapper.lang == default_kwargs["lang"]
        assert wrapper.load_all_available_meta == default_kwargs["load_all_available_meta"]
        assert wrapper.doc_content_chars_max == default_kwargs["doc_content_chars_max"]
