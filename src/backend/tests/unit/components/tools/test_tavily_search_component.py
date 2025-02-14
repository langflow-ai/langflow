import pytest
from langflow.components.tools import TavilySearchToolComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestTavilySearchToolComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return TavilySearchToolComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "query": "latest news",
            "search_depth": "advanced",
            "topic": "general",
            "max_results": 5,
            "include_images": True,
            "include_answer": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "tavily_search", "file_name": "TavilySearchToolComponent"},
        ]

    async def test_run_model_with_valid_input(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert result is not None
        assert isinstance(result, list)

    async def test_run_model_with_invalid_search_depth(self, component_class):
        component = component_class(api_key="test_api_key", query="latest news", search_depth="invalid_depth")
        result = component.run_model()
        assert result[0].data["error"] == "Invalid search depth value: 'invalid_depth'"

    async def test_run_model_with_invalid_topic(self, component_class):
        component = component_class(api_key="test_api_key", query="latest news", topic="invalid_topic")
        result = component.run_model()
        assert result[0].data["error"] == "Invalid topic value: 'invalid_topic'"

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "tavily_search"
        assert tool.description == "Perform a web search using the Tavily API."
