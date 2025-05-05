import pytest
from langflow.components.tools import WikipediaComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestWikipediaComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return WikipediaComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Python programming",
            "lang": "en",
            "k": 4,
            "load_all_available_meta": False,
            "doc_content_chars_max": 4000,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "wikipedia", "file_name": "Wikipedia"},
        ]

    async def test_fetch_content(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.fetch_content()
        assert isinstance(result, list)
        assert all(isinstance(item, Data) for item in result)

    async def test_fetch_content_text(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.fetch_content_text()
        assert isinstance(result, Message)
        assert isinstance(result.text, str)
        assert len(result.text) > 0

    async def test_build_wrapper(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        wrapper = component._build_wrapper()
        assert wrapper.top_k_results == default_kwargs["k"]
        assert wrapper.lang == default_kwargs["lang"]
        assert wrapper.load_all_available_meta == default_kwargs["load_all_available_meta"]
        assert wrapper.doc_content_chars_max == default_kwargs["doc_content_chars_max"]
