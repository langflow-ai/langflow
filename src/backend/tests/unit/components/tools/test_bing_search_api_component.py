import pytest

from langflow.components.tools import BingSearchAPIComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestBingSearchAPIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return BingSearchAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "bing_subscription_key": "test_key",
            "input_value": "OpenAI",
            "bing_search_url": "https://api.bing.microsoft.com/v7.0/search",
            "k": 4,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "bing_search_api", "file_name": "BingSearchAPI"},
        ]

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert isinstance(result, list)
        assert all(isinstance(data, dict) for data in result)
        assert all("snippet" in data for data in result)

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.num_results == default_kwargs["k"]
