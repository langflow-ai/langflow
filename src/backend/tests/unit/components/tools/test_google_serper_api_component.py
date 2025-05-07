import pytest
from langflow.components.tools import GoogleSerperAPIComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGoogleSerperAPIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GoogleSerperAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "serper_api_key": "test_api_key",
            "query": "test query",
            "k": 4,
            "query_type": "search",
            "query_params": {"gl": "us", "hl": "en"},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "google_serper_api", "file_name": "GoogleSerperAPI"},
        ]

    async def test_run_model(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = component.run_model()
        assert isinstance(result, list), "Expected result to be a list."
        assert all(isinstance(data, dict) for data in result), "Expected all items in result to be dictionaries."

    async def test_build_tool(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        tool = component.build_tool()
        assert tool.name == "google_search", "Tool name should be 'google_search'."
        assert tool.description == "Search Google for recent results.", "Tool description mismatch."
        assert tool.func == component._search, "Tool function should match the component's _search method."
