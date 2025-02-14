import pytest

from langflow.components.tools import SerpComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSerpComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SerpComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "serpapi_api_key": "test_api_key",
            "input_value": "OpenAI",
            "search_params": {"engine": "google"},
            "max_results": 5,
            "max_snippet_length": 100,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "serp", "file_name": "Serp"},
        ]

    async def test_fetch_content(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.fetch_content()
        assert isinstance(result, list)
        assert all(isinstance(data, dict) for data in result)

    async def test_fetch_content_text(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.fetch_content_text()
        assert isinstance(result, Message)
        assert isinstance(result.text, str)

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.run_model()
        assert isinstance(result, list)
        assert all(isinstance(data, Data) for data in result)

    async def test_invalid_api_key(self, component_class):
        component = component_class(
            serpapi_api_key="invalid_key",
            input_value="OpenAI",
            search_params={"engine": "google"},
            max_results=5,
            max_snippet_length=100,
        )
        with pytest.raises(ToolException):
            await component.fetch_content()
