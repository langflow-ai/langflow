import pytest

from langflow.components.tools import SearXNGToolComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSearXNGToolComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SearXNGToolComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"url": "http://localhost", "max_results": 10, "categories": [], "language": ""}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "searxng", "file_name": "SearXNGTool"},
        ]

    async def test_update_build_config_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"categories": {"options": [], "value": []}, "language": {"options": []}}
        updated_config = component.update_build_config(build_config, "http://localhost", "url")
        assert "categories" in updated_config
        assert "language" in updated_config

    async def test_update_build_config_failure(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"categories": {"options": [], "value": []}, "language": {"options": []}}
        updated_config = component.update_build_config(build_config, "invalid_url", "url")
        assert "Failed to parse" in updated_config["categories"]["options"]

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "searxng_search_tool"

    async def test_tool_search(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        results = tool.search("test query")
        assert isinstance(results, list)
