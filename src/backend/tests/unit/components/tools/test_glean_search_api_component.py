import pytest

from langflow.components.tools import GleanSearchAPIComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGleanSearchAPIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GleanSearchAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "glean_api_url": "https://api.glean.com/",
            "glean_access_token": "test_access_token",
            "query": "test query",
            "page_size": 10,
            "request_options": {},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "glean_search_api", "file_name": "GleanSearchAPI"},
        ]

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.run_model()
        assert result is not None
        assert isinstance(result, list)

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "glean_search_api"

    async def test_invalid_query(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.query = ""  # Set an invalid query
        with pytest.raises(ToolException):
            await component.run_model()
