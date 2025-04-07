import os

import pytest
from langflow.components.Notion import NotionUserList
from tests.base import ComponentTestBaseWithClient

API_KEY = "NotionSecret"


@pytest.mark.skipif(
    not os.environ.get(API_KEY),
    reason="Environment variable '{API_KEY}' is not defined.",
)
@pytest.mark.usefixtures("client")
class TestNotionUserListComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NotionUserList

    @pytest.fixture
    def default_kwargs(self):
        return {"notion_secret": os.environ.get(API_KEY)}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "notion", "file_name": "NotionUserList"},
        ]

    def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert isinstance(result, list)
        assert all(isinstance(record, dict) for record in result)

    def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "notion_list_users"
        assert tool.description == "Retrieve users from Notion."
