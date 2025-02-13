import pytest

from langflow.components.firecrawl import FirecrawlCrawlApi
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestFirecrawlCrawlApi(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return FirecrawlCrawlApi

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "url": "https://example.com",
            "timeout": 5000,
            "idempotency_key": None,
            "crawlerOptions": {"data": {"option1": "value1"}},
            "scrapeOptions": {"data": {"option2": "value2"}},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "firecrawl", "file_name": "FirecrawlCrawlApi"},
        ]

    async def test_crawl_api_success(self, component_class, default_kwargs):
        # Arrange
        component = await self.component_setup(component_class, default_kwargs)

        # Act
        result = await component.run()

        # Assert
        assert result is not None
        assert "results" in result.data
        assert isinstance(result.data["results"], dict)

    async def test_crawl_api_with_idempotency_key(self, component_class, default_kwargs):
        # Arrange
        default_kwargs["idempotency_key"] = "unique_key"
        component = await self.component_setup(component_class, default_kwargs)

        # Act
        result = await component.run()

        # Assert
        assert result is not None
        assert "results" in result.data
        assert isinstance(result.data["results"], dict)

    async def test_crawl_api_import_error(self, component_class, default_kwargs):
        # Arrange
        with pytest.raises(ImportError, match="Could not import firecrawl integration package"):
            component = component_class(**default_kwargs)
            component.crawl()
