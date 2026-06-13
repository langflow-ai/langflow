"""Unit tests for the fastCRW components.

fastCRW is Firecrawl-compatible, so these components mirror the Firecrawl provider
and drive the official ``firecrawl`` client at the fastCRW base URL. The tests mock
``firecrawl.FirecrawlApp`` so no network calls are made.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from lfx.components.crw import (
    CrwCrawlApi,
    CrwMapApi,
    CrwScrapeApi,
    CrwSearchApi,
)
from lfx.components.crw.crw_scrape_api import DEFAULT_API_URL
from lfx.schema.data import Data


@pytest.fixture
def mock_firecrawl():
    """Mock the ``firecrawl`` package so components run without the SDK or network."""
    app_instance = MagicMock()
    app_instance.scrape_url.return_value = {"success": True, "markdown": "# Hello"}
    app_instance.crawl_url.return_value = {"success": True, "data": [{"markdown": "# Page"}]}
    app_instance.map_url.return_value = {"success": True, "links": ["https://example.com/a"]}
    app_instance.search.return_value = {"success": True, "data": [{"url": "https://example.com"}]}

    firecrawl_app = MagicMock(return_value=app_instance)
    mock_module = MagicMock()
    mock_module.FirecrawlApp = firecrawl_app

    with patch.dict(sys.modules, {"firecrawl": mock_module}):
        yield firecrawl_app, app_instance


def test_default_api_url_points_to_cloud():
    """The default base URL should target the fastCRW managed cloud."""
    assert DEFAULT_API_URL == "https://fastcrw.com/api"


def test_scrape_uses_default_base_url(mock_firecrawl):
    firecrawl_app, app_instance = mock_firecrawl
    component = CrwScrapeApi()
    component.set_attributes({"api_key": "test-key", "url": "https://example.com"})

    result = component.scrape()

    assert isinstance(result, Data)
    assert result.data["markdown"] == "# Hello"
    firecrawl_app.assert_called_once_with(api_key="test-key", api_url=DEFAULT_API_URL)
    app_instance.scrape_url.assert_called_once()


def test_scrape_allows_self_host_override(mock_firecrawl):
    firecrawl_app, _ = mock_firecrawl
    component = CrwScrapeApi()
    component.set_attributes({"api_key": "", "api_url": "http://localhost:3000", "url": "https://example.com"})

    component.scrape()

    firecrawl_app.assert_called_once_with(api_key="", api_url="http://localhost:3000")


def test_crawl_uses_default_base_url(mock_firecrawl):
    firecrawl_app, app_instance = mock_firecrawl
    component = CrwCrawlApi()
    component.set_attributes({"api_key": "test-key", "url": "https://example.com"})

    result = component.crawl()

    assert isinstance(result, Data)
    assert "results" in result.data
    firecrawl_app.assert_called_once_with(api_key="test-key", api_url=DEFAULT_API_URL)
    app_instance.crawl_url.assert_called_once()


def test_map_uses_default_base_url(mock_firecrawl):
    firecrawl_app, app_instance = mock_firecrawl
    component = CrwMapApi()
    component.set_attributes({"api_key": "test-key", "urls": "https://example.com"})

    result = component.map()

    assert isinstance(result, Data)
    assert result.data["success"] is True
    assert result.data["links"] == ["https://example.com/a"]
    firecrawl_app.assert_called_once_with(api_key="test-key", api_url=DEFAULT_API_URL)
    app_instance.map_url.assert_called_once()


@pytest.mark.usefixtures("mock_firecrawl")
def test_map_requires_urls():
    component = CrwMapApi()
    component.set_attributes({"api_key": "test-key", "urls": ""})

    with pytest.raises(ValueError, match="URLs are required"):
        component.map()


def test_search_uses_default_base_url(mock_firecrawl):
    firecrawl_app, app_instance = mock_firecrawl
    component = CrwSearchApi()
    component.set_attributes({"api_key": "test-key", "query": "langflow"})

    result = component.search()

    assert isinstance(result, Data)
    assert result.data["success"] is True
    firecrawl_app.assert_called_once_with(api_key="test-key", api_url=DEFAULT_API_URL)
    app_instance.search.assert_called_once()


@pytest.mark.usefixtures("mock_firecrawl")
def test_search_requires_query():
    component = CrwSearchApi()
    component.set_attributes({"api_key": "test-key", "query": ""})

    with pytest.raises(ValueError, match="Query is required"):
        component.search()
