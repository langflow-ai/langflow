"""Unit tests for the Firecrawl components (firecrawl-py v2 / v4 SDK).

These verify v2 SDK usage, the v1->v2 parameter mapping, response
serialization, and error handling using a mocked Firecrawl SDK. No network
access or real ``firecrawl-py`` install is required: the SDK is injected via
``sys.modules`` so the components' in-method ``from firecrawl import ...``
statements resolve to the mocks.
"""

import sys
import types
from unittest.mock import MagicMock

import pytest
from lfx.components.firecrawl.firecrawl_crawl_api import FirecrawlCrawlApi
from lfx.components.firecrawl.firecrawl_extract_api import FirecrawlExtractApi
from lfx.components.firecrawl.firecrawl_map_api import FirecrawlMapApi
from lfx.components.firecrawl.firecrawl_scrape_api import FirecrawlScrapeApi
from lfx.components.firecrawl.firecrawl_search_api import FirecrawlSearchApi


@pytest.fixture
def mock_firecrawl(monkeypatch):
    """Inject a fake ``firecrawl`` SDK and return the mocked ``Firecrawl`` class.

    ``mock_firecrawl.return_value`` is the client instance whose
    ``.scrape``/``.crawl``/``.map``/``.extract``/``.search`` methods can be
    stubbed per test.
    """
    client_cls = MagicMock(name="Firecrawl")

    firecrawl_mod = types.ModuleType("firecrawl")
    firecrawl_mod.Firecrawl = client_cls

    v2_mod = types.ModuleType("firecrawl.v2")
    types_mod = types.ModuleType("firecrawl.v2.types")
    types_mod.ScrapeOptions = MagicMock(name="ScrapeOptions")
    v2_mod.types = types_mod

    monkeypatch.setitem(sys.modules, "firecrawl", firecrawl_mod)
    monkeypatch.setitem(sys.modules, "firecrawl.v2", v2_mod)
    monkeypatch.setitem(sys.modules, "firecrawl.v2.types", types_mod)
    return client_cls


def _typed(dump):
    """Return a fake v2 typed response whose ``model_dump()`` yields ``dump``."""
    obj = MagicMock()
    obj.model_dump.return_value = dump
    return obj


class TestFirecrawlScrapeApi:
    def test_scrape_calls_v2_and_serializes(self, mock_firecrawl):
        client = mock_firecrawl.return_value
        client.scrape.return_value = _typed({"markdown": "# Hi", "metadata": {}})

        comp = FirecrawlScrapeApi()
        comp.api_key = "test-key"
        comp.url = "https://example.com"
        comp.timeout = 0
        comp.scrapeOptions = None
        comp.extractorOptions = None

        result = comp.scrape()

        mock_firecrawl.assert_called_once_with(api_key="test-key")
        client.scrape.assert_called_once()
        assert client.scrape.call_args.args[0] == "https://example.com"
        assert result.data == {"markdown": "# Hi", "metadata": {}}

    def test_scrape_propagates_sdk_error(self, mock_firecrawl):
        client = mock_firecrawl.return_value
        client.scrape.side_effect = RuntimeError("boom")

        comp = FirecrawlScrapeApi()
        comp.api_key = "k"
        comp.url = "https://example.com"
        comp.timeout = 0
        comp.scrapeOptions = None
        comp.extractorOptions = None

        with pytest.raises(RuntimeError):
            comp.scrape()


class TestFirecrawlCrawlApi:
    def test_crawl_maps_legacy_params_and_serializes(self, mock_firecrawl):
        client = mock_firecrawl.return_value
        client.crawl.return_value = _typed({"status": "completed", "data": []})

        comp = FirecrawlCrawlApi()
        comp.api_key = "test-key"
        comp.url = "https://example.com"
        comp.timeout = 0
        comp.idempotency_key = ""
        comp.crawlerOptions = None
        comp.scrapeOptions = None

        result = comp.crawl()

        mock_firecrawl.assert_called_once_with(api_key="test-key")
        client.crawl.assert_called_once()
        assert client.crawl.call_args.args[0] == "https://example.com"
        kwargs = client.crawl.call_args.kwargs
        # v1 "maxDepth" was renamed to v2 "max_discovery_depth".
        assert "max_discovery_depth" in kwargs
        assert "max_depth" not in kwargs
        # v1 "allowBackwardLinks" was renamed to v2 "crawl_entire_domain".
        assert "crawl_entire_domain" in kwargs
        assert result.data["results"] == {"status": "completed", "data": []}


class TestFirecrawlMapApi:
    def test_map_sitemap_only_maps_to_enum(self, mock_firecrawl):
        client = mock_firecrawl.return_value
        link = _typed({"url": "https://example.com/a"})
        result_obj = MagicMock()
        result_obj.links = [link]
        client.map.return_value = result_obj

        comp = FirecrawlMapApi()
        comp.api_key = "test-key"
        comp.urls = "https://example.com"
        comp.ignore_sitemap = False
        comp.sitemap_only = True
        comp.include_subdomains = False

        result = comp.map()

        client.map.assert_called_once()
        assert client.map.call_args.kwargs.get("sitemap") == "only"
        assert result.data["links"] == [{"url": "https://example.com/a"}]

    def test_map_ignore_sitemap_maps_to_skip(self, mock_firecrawl):
        client = mock_firecrawl.return_value
        result_obj = MagicMock()
        result_obj.links = []
        client.map.return_value = result_obj

        comp = FirecrawlMapApi()
        comp.api_key = "k"
        comp.urls = "https://example.com"
        comp.ignore_sitemap = True
        comp.sitemap_only = False
        comp.include_subdomains = False

        comp.map()

        assert client.map.call_args.kwargs.get("sitemap") == "skip"


class TestFirecrawlExtractApi:
    def test_extract_calls_v2_with_urls_list_and_web_search(self, mock_firecrawl):
        client = mock_firecrawl.return_value
        client.extract.return_value = _typed({"data": {"x": 1}})

        comp = FirecrawlExtractApi()
        comp.api_key = "test-key"
        comp.urls = "https://example.com"
        comp.prompt = "extract the title"
        comp.schema = None
        comp.enable_web_search = True

        result = comp.extract()

        client.extract.assert_called_once()
        # v2 takes the URLs as a list in the first positional arg.
        assert client.extract.call_args.args[0] == ["https://example.com"]
        assert client.extract.call_args.kwargs.get("enable_web_search") is True
        assert result.data == {"data": {"x": 1}}


class TestFirecrawlSearchApi:
    def test_search_calls_v2_with_query_limit_location(self, mock_firecrawl):
        client = mock_firecrawl.return_value
        client.search.return_value = _typed({"web": [{"url": "https://example.com"}]})

        comp = FirecrawlSearchApi()
        comp.api_key = "test-key"
        comp.query = "firecrawl"
        comp.limit = 5
        comp.location = "US"

        result = comp.search()

        mock_firecrawl.assert_called_once_with(api_key="test-key")
        client.search.assert_called_once()
        assert client.search.call_args.args[0] == "firecrawl"
        assert client.search.call_args.kwargs.get("limit") == 5
        assert client.search.call_args.kwargs.get("location") == "US"
        assert result.data == {"web": [{"url": "https://example.com"}]}
