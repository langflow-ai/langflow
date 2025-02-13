import os

import pytest

from langflow.components.Notion import NotionPageContent
from langflow.schema import Data
from tests.base import ComponentTestBaseWithClient

API_KEY = "NotionSecret"


@pytest.mark.skipif(
    not os.environ.get(API_KEY),
    reason="Environment variable '{API_KEY}' is not defined.",
)
@pytest.mark.usefixtures("client")
class TestNotionPageContentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NotionPageContent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "page_id": "sample_page_id",
            "notion_secret": os.environ.get(API_KEY),
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_run_model_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert result is not None
        assert isinstance(result, Data)
        assert "content" in result.data

    def test_run_model_error(self, component_class, default_kwargs, mocker):
        mocker.patch.object(component_class, "_retrieve_page_content", return_value="Error: Page not found")
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert result is not None
        assert result.text == "Error: Page not found"

    def test_parse_blocks(self, component_class):
        component = component_class()
        blocks = [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hello World"}]}},
            {"type": "divider"},
            {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Heading"}]}},
        ]
        content = component.parse_blocks(blocks)
        assert content == "Hello World\n\n---\n\nHeading\n\n"

    def test_parse_rich_text(self, component_class):
        component = component_class()
        rich_text = [{"plain_text": "Hello"}, {"plain_text": " "}, {"plain_text": "World"}]
        content = component.parse_rich_text(rich_text)
        assert content == "Hello World"

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
