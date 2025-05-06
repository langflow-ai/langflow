import pytest
from langflow.components.scrapegraph import ScrapeGraphSmartScraperApi
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestScrapeGraphSmartScraperApi(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ScrapeGraphSmartScraperApi

    @pytest.fixture
    def default_kwargs(self):
        return {"api_key": "test_api_key", "url": "https://example.com"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "scrape_graph_smart_scraper_api", "file_name": "ScrapeGraphSmartScraperApi"},
        ]

    async def test_scrape_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.scrape()
        assert result is not None
        assert isinstance(result, list)
        assert all(isinstance(data, dict) for data in result)

    async def test_scrape_import_error(self, component_class):
        with pytest.raises(ImportError, match="Could not import scrapegraph-py package"):
            component = component_class(api_key="test_api_key", url="https://example.com")
            component.scrape()

    async def test_scrape_invalid_url(self, component_class):
        component = component_class(api_key="test_api_key", url="invalid_url")
        with pytest.raises(Exception):
            await component.scrape()
