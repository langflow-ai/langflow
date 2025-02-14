import pytest
from langflow.components.tools import SerpAPIComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSerpAPIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SerpAPIComponent

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
            {"version": "1.0.0", "module": "serp_api", "file_name": "SerpAPI"},
            {"version": "1.1.0", "module": "serp_api", "file_name": "serp_api"},
        ]

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "serp_search_api"
        assert tool.description == "Search for recent results using SerpAPI with result limiting"

    async def test_run_model_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        results = await component.run_model()
        assert isinstance(results, list)
        assert all(isinstance(result, dict) for result in results)

    async def test_run_model_error(self, component_class):
        component = component_class(serpapi_api_key="invalid_key", input_value="OpenAI")
        results = await component.run_model()
        assert len(results) == 1
        assert "error" in results[0].data
        assert "Error" in component.status
