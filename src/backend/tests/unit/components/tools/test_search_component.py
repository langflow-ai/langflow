import pytest

from langflow.components.tools import SearchComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSearchComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SearchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "engine": "google",
            "api_key": "test_api_key",
            "input_value": "OpenAI",
            "search_params": {},
            "max_results": 5,
            "max_snippet_length": 100,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "search", "file_name": "SearchComponent"},
        ]

    async def test_fetch_content(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        results = await component.fetch_content()
        assert isinstance(results, list)
        assert all(isinstance(result, Data) for result in results)

    async def test_fetch_content_text(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result_message = await component.fetch_content_text()
        assert isinstance(result_message, Message)
        assert isinstance(result_message.text, str)

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        results = await component.run_model()
        assert isinstance(results, list)
        assert all(isinstance(result, Data) for result in results)

    async def test_invalid_api_key(self, component_class):
        component = component_class(api_key="invalid_key")
        with pytest.raises(Exception):
            await component.fetch_content()
