import pytest
from langflow.components.scrapegraph import ScrapeGraphMarkdownifyApi
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestScrapeGraphMarkdownifyApi(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ScrapeGraphMarkdownifyApi

    @pytest.fixture
    def default_kwargs(self):
        return {"api_key": "test_api_key", "url": "https://example.com"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "scrape_graph_markdownify_api", "file_name": "ScrapeGraphMarkdownifyApi"},
        ]

    async def test_scrape_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.scrape()
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0  # Assuming the response should contain data

    async def test_scrape_import_error(self, component_class):
        with pytest.raises(ImportError, match="Could not import scrapegraph-py package"):
            component = component_class(api_key="test_api_key", url="https://example.com")
            component.scrape()

    async def test_scrape_invalid_url(self, component_class):
        component = component_class(api_key="test_api_key", url="invalid_url")
        with pytest.raises(Exception):
            await component.scrape()
