import pytest
from langflow.components.confluence import ConfluenceComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestConfluenceComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ConfluenceComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "url": "https://example.atlassian.net/wiki",
            "username": "email@example.com",
            "api_key": "test_api_key",
            "space_key": "TEST_SPACE",
            "cloud": True,
            "content_format": "storage",
            "max_pages": 1000,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "confluence", "file_name": "Confluence"},
        ]

    async def test_load_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.load_documents()
        assert isinstance(result, list), "Expected result to be a list."
        assert all(isinstance(doc, Data) for doc in result), "All items in result should be instances of Data."

    async def test_build_confluence(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        confluence_loader = component.build_confluence()
        assert confluence_loader.url == default_kwargs["url"]
        assert confluence_loader.username == default_kwargs["username"]
        assert confluence_loader.api_key == default_kwargs["api_key"]
        assert confluence_loader.space_key == default_kwargs["space_key"]
        assert confluence_loader.cloud == default_kwargs["cloud"]
        assert confluence_loader.content_format == ContentFormat(default_kwargs["content_format"])
        assert confluence_loader.max_pages == default_kwargs["max_pages"]
