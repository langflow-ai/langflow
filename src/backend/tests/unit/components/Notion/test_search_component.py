import os

import pytest

from langflow.components.Notion import NotionSearch
from tests.base import ComponentTestBaseWithoutClient

API_KEY = "NotionSecret"


@pytest.mark.skipif(
    not os.environ.get(API_KEY),
    reason="Environment variable '{API_KEY}' is not defined.",
)
class TestNotionSearchComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return NotionSearch

    @pytest.fixture
    def default_kwargs(self):
        return {
            "notion_secret": os.environ.get(API_KEY),
            "query": "test query",
            "filter_value": "page",
            "sort_direction": "descending",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        results = await component.run_model()
        assert isinstance(results, list)
        assert all(isinstance(record, dict) for record in results)

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "notion_search"
        assert tool.description.startswith("Search Notion pages and databases.")

    async def test_search_notion(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        results = await component._search_notion(
            default_kwargs["query"], default_kwargs["filter_value"], default_kwargs["sort_direction"]
        )
        assert isinstance(results, list)
        assert all("id" in result for result in results)
        assert all("object" in result for result in results)
