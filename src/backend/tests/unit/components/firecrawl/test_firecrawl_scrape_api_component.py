import pytest
from langflow.components.firecrawl import FirecrawlScrapeApi
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestFirecrawlScrapeApi(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return FirecrawlScrapeApi

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "url": "https://example.com",
            "timeout": 5000,
            "scrapeOptions": {"data": {"option1": "value1"}},
            "extractorOptions": {"data": {"extractor1": "value1"}},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "firecrawl", "file_name": "FirecrawlScrapeApi"},
        ]

    async def test_crawl_method(self, component_class, default_kwargs):
        # Arrange
        component = await self.component_setup(component_class, default_kwargs)

        # Act
        result = await component.run()

        # Assert
        assert result is not None
        assert isinstance(result, list)
        assert all(isinstance(item, Data) for item in result)

    def test_all_versions_have_a_file_name_defined(self, file_names_mapping):
        # Arrange
        if not file_names_mapping:
            pytest.skip("No file names mapping defined for this component.")

        # Act & Assert
        super().test_all_versions_have_a_file_name_defined(file_names_mapping)

    @pytest.mark.parametrize("version", ["1.0.0"])
    def test_component_versions(self, version, default_kwargs, file_names_mapping):
        # Arrange
        if not file_names_mapping:
            pytest.skip("No file names mapping defined for this component.")

        # Act & Assert
        super().test_component_versions(version, default_kwargs, file_names_mapping)
