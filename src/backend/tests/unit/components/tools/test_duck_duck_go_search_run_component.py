import pytest
from langflow.components.tools import DuckDuckGoSearchComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestDuckDuckGoSearchComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return DuckDuckGoSearchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "OpenAI",
            "max_results": 5,
            "max_snippet_length": 100,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "duckduckgo_search", "file_name": "DuckDuckGoSearch"},
        ]

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "duckduckgo_search"
        assert tool.description == "Search for recent results using DuckDuckGo with result limiting"

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        results = component.run_model()
        assert results is not None
        assert isinstance(results, list)
        assert all(isinstance(result, dict) for result in results)
        assert all("snippet" in result for result in results)

    async def test_tool_exception_handling(self, component_class):
        component = component_class(input_value="", max_results=5, max_snippet_length=100)
        with pytest.raises(ToolException):
            component.run_model()
