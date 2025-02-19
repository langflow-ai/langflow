import os

import pytest
from langflow.components.Notion import NotionPageCreator
from tests.base import ComponentTestBaseWithClient

API_KEY = "NotionSecret"


@pytest.mark.skipif(
    not os.environ.get(API_KEY),
    reason="Environment variable '{API_KEY}' is not defined.",
)
@pytest.mark.usefixtures("client")
class TestNotionPageCreator(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NotionPageCreator

    @pytest.fixture
    def default_kwargs(self):
        return {
            "database_id": "test_database_id",
            "notion_secret": os.environ.get(API_KEY),
            "properties_json": '{"Name": {"title": [{"text": {"content": "Test Page"}}]}}',
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_run_model_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert result is not None
        assert "Created page properties:" in result.text

    def test_run_model_invalid_database_id(self, component_class, default_kwargs):
        component = component_class(
            database_id="",
            notion_secret=default_kwargs.get("notion_secret"),
            properties_json="{}",
        )
        result = component.run_model()
        assert result.text == "Invalid input. Please provide 'database_id' and 'properties_json'."

    def test_run_model_invalid_properties_json(self, component_class, default_kwargs):
        component = component_class(
            database_id="test_database_id",
            notion_secret=default_kwargs.get("notion_secret"),
            properties_json="invalid_json",
        )
        result = component.run_model()
        assert "Invalid properties format." in result.text

    def test_create_notion_page_invalid_input(self, component_class):
        component = component_class(database_id="", properties_json="")
        result = component._create_notion_page("", "")
        assert result == "Invalid input. Please provide 'database_id' and 'properties_json'."

    def test_create_notion_page_json_decode_error(self, component_class):
        component = component_class(database_id="test_database_id", properties_json="invalid_json")
        result = component._create_notion_page(component.database_id, component.properties_json)
        assert "Invalid properties format." in result
