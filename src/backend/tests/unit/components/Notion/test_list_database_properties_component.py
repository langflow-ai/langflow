import os

import pytest
from langflow.components.Notion import NotionDatabaseProperties
from tests.base import ComponentTestBaseWithClient

API_KEY = "NotionSecret"


@pytest.mark.skipif(
    not os.environ.get(API_KEY),
    reason="Environment variable '{API_KEY}' is not defined.",
)
@pytest.mark.usefixtures("client")
class TestNotionDatabaseProperties(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NotionDatabaseProperties

    @pytest.fixture
    def default_kwargs(self):
        return {"database_id": "test_database_id", "notion_secret": os.environ.get(API_KEY)}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "notion", "file_name": "NotionDatabaseProperties"},
        ]

    def test_run_model_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert result is not None
        assert isinstance(result.text, str)
        assert isinstance(result.data, dict)

    def test_run_model_failure(self, component_class, default_kwargs):
        component = component_class(
            database_id="invalid_id",
            notion_secret=default_kwargs.get("notion_secret"),
        )
        result = component.run_model()
        assert result is not None
        assert isinstance(result.text, str)
        assert "Error fetching Notion database properties" in result.text

    def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "notion_database_properties"
        assert tool.description == "Retrieve properties of a Notion database. Input should include the database ID."
