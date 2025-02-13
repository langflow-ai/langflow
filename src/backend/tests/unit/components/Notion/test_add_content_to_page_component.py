import os

import pytest
from langflow.components.Notion import AddContentToPage
from tests.base import ComponentTestBaseWithClient

API_KEY = "NotionSecret"


@pytest.mark.skipif(
    not os.environ.get(API_KEY),
    reason="Environment variable '{API_KEY}' is not defined.",
)
@pytest.mark.usefixtures("client")
class TestAddContentToPageComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AddContentToPage

    @pytest.fixture
    def default_kwargs(self):
        return {
            "markdonw_text": "Sample text",
            "block_id": "block_id",
            "notion_secret": os.environ.get(API_KEY),
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert result is not None
        assert isinstance(result.data, dict)
        assert "object" in result.data

    def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "add_content_to_notion_page"
        assert tool.description == "Convert markdown text to Notion blocks and append them to a Notion page."

    def test_create_block(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        block = component.create_block("paragraph", "Sample text")
        assert block["object"] == "block"
        assert block["type"] == "paragraph"
        assert block["paragraph"]["rich_text"][0]["text"]["content"] == "Sample text"
