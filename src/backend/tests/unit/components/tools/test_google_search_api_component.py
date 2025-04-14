import pytest
from langflow.components.tools import GoogleSearchAPIComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGoogleSearchAPIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GoogleSearchAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "google_api_key": "test_api_key",
            "google_cse_id": "test_cse_id",
            "input_value": "OpenAI",
            "k": 4,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert result is not None
        assert isinstance(result, list)
        assert all(isinstance(data, dict) for data in result)

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "google_search"
        assert tool.description == "Search Google for recent results."
        assert callable(tool.func)
