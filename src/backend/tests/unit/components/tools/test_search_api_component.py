import pytest

from langflow.components.tools import SearchAPIComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSearchAPIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SearchAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "engine": "google",
            "api_key": "test_api_key",
            "input_value": "example search",
            "search_params": {},
            "max_results": 5,
            "max_snippet_length": 100,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "search_api"
        assert tool.description == "Search for recent results using searchapi.io with result limiting"

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        results = component.run_model()
        assert isinstance(results, list)
        assert all(isinstance(data, dict) for data in results)
        assert all("snippet" in data for data in results)

    async def test_status_after_run(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.run_model()
        assert component.status is not None
        assert isinstance(component.status, list)
