import os

import pytest
from langflow.components.Notion import NotionPageUpdate
from tests.base import ComponentTestBaseWithClient

API_KEY = "NotionSecret"


@pytest.mark.skipif(
    not os.environ.get(API_KEY),
    reason="Environment variable '{API_KEY}' is not defined.",
)
@pytest.mark.usefixtures("client")
class TestNotionPageUpdateComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NotionPageUpdate

    @pytest.fixture
    def default_kwargs(self):
        return {
            "page_id": "example_page_id",
            "properties": '{"title": {"title": [{"text": {"content": "Updated Title"}}]}}',
            "notion_secret": os.environ.get(API_KEY),
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "notion", "file_name": "NotionPageUpdate"},
        ]

    def test_run_model_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert result is not None
        assert "Updated page properties:" in result.text

    def test_run_model_invalid_json(self, component_class):
        invalid_kwargs = {
            "page_id": "example_page_id",
            "properties": "invalid_json",
            "notion_secret": "example_notion_secret",
        }
        component = component_class(**invalid_kwargs)
        result = component.run_model()
        assert result.text == "Invalid JSON format for properties: Expecting value: line 1 column 1 (char 0)"
