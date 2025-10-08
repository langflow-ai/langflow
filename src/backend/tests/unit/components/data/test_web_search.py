from unittest.mock import Mock, patch

import pandas as pd
import pytest
from lfx.components.data.web_search import WebSearchComponent
from lfx.schema import DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestWebSearchComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return WebSearchComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "search_mode": "Web",
            "query": "OpenAI GPT-4",
            "timeout": 5,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for the component."""
        return []

    async def test_invalid_url_handling(self):
        """Test invalid URL handling."""
        component = WebSearchComponent()

        # Test invalid URL
        invalid_url = "htp://invalid-url"

        # Ensure the URL is invalid
        with pytest.raises(ValueError, match="Invalid URL"):
            component.ensure_url(invalid_url)

    def test_validate_url(self):
        """Test URL validation."""
        component = WebSearchComponent()

        # Valid URLs
        assert component.validate_url("https://example.com")
        assert component.validate_url("http://example.com")
        assert component.validate_url("www.example.com")
        assert component.validate_url("example.com")
        assert component.validate_url("https://subdomain.example.co.uk")

        # Invalid URLs
        assert not component.validate_url("not a url at all")
        assert not component.validate_url("://missing-protocol")

    def test_ensure_url(self):
        """Test ensure_url adds protocol if missing."""
        component = WebSearchComponent()

        assert component.ensure_url("https://example.com") == "https://example.com"
        assert component.ensure_url("http://example.com") == "http://example.com"
        assert component.ensure_url("example.com") == "https://example.com"
        assert component.ensure_url("www.example.com") == "https://www.example.com"

    def test_sanitize_query(self):
        """Test query sanitization."""
        component = WebSearchComponent()

        # Test removal of dangerous characters
        assert component._sanitize_query('<script>alert("test")</script>') == "scriptalert(test)/script"
        assert component._sanitize_query("test'query\"with<dangerous>chars") == "testquerywithdangerouschars"
        assert component._sanitize_query("  normal query  ") == "normal query"

    def test_clean_html(self):
        """Test HTML cleaning."""
        component = WebSearchComponent()

        html = '<p>This is <b>bold</b> text with <a href="#">link</a></p>'
        expected = "This is bold text with link"
        assert component.clean_html(html) == expected

        # Test with complex HTML
        html = "<div><h1>Title</h1><p>Paragraph</p></div>"
        expected = "Title Paragraph"
        assert component.clean_html(html) == expected

    def test_update_build_config_web_mode(self):
        """Test build config update for Web mode."""
        component = WebSearchComponent()
        build_config = {"query": {"info": "", "display_name": ""}}

        result = component.update_build_config(build_config, "Web", "search_mode")
        assert result["query"]["info"] == "Keywords to search for"
        assert result["query"]["display_name"] == "Search Query"

    def test_update_build_config_news_mode(self):
        """Test build config update for News mode."""
        component = WebSearchComponent()
        build_config = {"query": {"info": "", "display_name": ""}}

        result = component.update_build_config(build_config, "News", "search_mode")
        assert result["query"]["info"] == "Search keywords for news articles."
        assert result["query"]["display_name"] == "Search Query"

    def test_update_build_config_rss_mode(self):
        """Test build config update for RSS mode."""
        component = WebSearchComponent()
        build_config = {"query": {"info": "", "display_name": ""}}

        result = component.update_build_config(build_config, "RSS", "search_mode")
        assert result["query"]["info"] == "RSS feed URL to parse"
        assert result["query"]["display_name"] == "RSS Feed URL"

    @patch("lfx.components.data.web_search.requests.get")
    def test_perform_web_search_success(self, mock_get):
        """Test successful web search."""
        component = WebSearchComponent()
        component.query = "test query"
        component.timeout = 5

        # Mock DuckDuckGo response
        mock_response = Mock()
        mock_response.text = """
        <html>
            <div class="result">
                <a class="result__a" href="?uddg=https%3A%2F%2Fexample.com">Test Title</a>
                <a class="result__snippet">Test snippet content</a>
            </div>
        </html>
        """
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status.return_value = None

        # Mock the page fetch
        mock_page_response = Mock()
        mock_page_response.text = "<html><body>Page content</body></html>"
        mock_page_response.raise_for_status.return_value = None

        mock_get.side_effect = [mock_response, mock_page_response]

        result = component.perform_web_search()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["title"] == "Test Title"
        assert result.iloc[0]["snippet"] == "Test snippet content"
        assert "Page content" in result.iloc[0]["content"]

    @patch("lfx.components.data.web_search.requests.get")
    def test_perform_web_search_no_results(self, mock_get):
        """Test web search with no results."""
        component = WebSearchComponent()
        component.query = "test query"
        component.timeout = 5

        mock_response = Mock()
        mock_response.text = ""
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status.return_value = None

        mock_get.return_value = mock_response

        result = component.perform_web_search()

        assert isinstance(result, DataFrame)
        assert "No results found" in result.iloc[0]["snippet"]

    @patch("lfx.components.data.web_search.requests.get")
    def test_perform_web_search_request_error(self, mock_get):
        """Test web search with request error."""
        component = WebSearchComponent()
        component.query = "test query"
        component.timeout = 5

        from requests import RequestException

        mock_get.side_effect = RequestException("Connection error")

        result = component.perform_web_search()

        assert isinstance(result, DataFrame)
        assert "Connection error" in result.iloc[0]["snippet"]

    @patch("lfx.components.data.web_search.requests.get")
    def test_perform_news_search_with_query(self, mock_get):
        """Test news search with query."""
        component = WebSearchComponent()
        component.query = "test news"
        component.timeout = 5

        # Mock RSS response
        mock_response = Mock()
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss>
            <channel>
                <item>
                    <title>Test News Title</title>
                    <link>https://news.example.com</link>
                    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
                    <description>Test news description</description>
                </item>
            </channel>
        </rss>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = component.perform_news_search()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["title"] == "Test News Title"
        assert result.iloc[0]["link"] == "https://news.example.com"
        assert result.iloc[0]["summary"] == "Test news description"

    @patch("lfx.components.data.web_search.requests.get")
    def test_perform_news_search_with_topic(self, mock_get):
        """Test news search with topic."""
        component = WebSearchComponent()
        component.topic = "TECHNOLOGY"
        component.timeout = 5

        # Mock RSS response
        mock_response = Mock()
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss>
            <channel>
                <item>
                    <title>Tech News</title>
                    <link>https://tech.example.com</link>
                    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
                    <description>Technology news</description>
                </item>
            </channel>
        </rss>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = component.perform_news_search()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        # Check that the URL was constructed with topic
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        assert "topic/TECHNOLOGY" in call_args

    @patch("lfx.components.data.web_search.requests.get")
    def test_perform_news_search_no_params(self, mock_get):  # noqa: ARG002
        """Test news search with no parameters."""
        component = WebSearchComponent()
        component.timeout = 5

        result = component.perform_news_search()

        assert isinstance(result, DataFrame)
        assert "No search parameters provided" in result.iloc[0]["summary"]

    @patch("lfx.components.data.web_search.requests.get")
    def test_perform_rss_read_success(self, mock_get):
        """Test successful RSS feed reading."""
        component = WebSearchComponent()
        component.query = "https://example.com/feed.rss"
        component.timeout = 5

        # Mock RSS response
        mock_response = Mock()
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss>
            <channel>
                <item>
                    <title>RSS Item 1</title>
                    <link>https://example.com/item1</link>
                    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
                    <description>Description 1</description>
                </item>
                <item>
                    <title>RSS Item 2</title>
                    <link>https://example.com/item2</link>
                    <pubDate>Tue, 02 Jan 2024 00:00:00 GMT</pubDate>
                    <description>Description 2</description>
                </item>
            </channel>
        </rss>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = component.perform_rss_read()

        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert result.iloc[0]["title"] == "RSS Item 1"
        assert result.iloc[1]["title"] == "RSS Item 2"

    @patch("lfx.components.data.web_search.requests.get")
    def test_perform_rss_read_empty_response(self, mock_get):
        """Test RSS read with empty response."""
        component = WebSearchComponent()
        component.query = "https://example.com/feed.rss"
        component.timeout = 5

        mock_response = Mock()
        mock_response.content = b""
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = component.perform_rss_read()

        assert isinstance(result, DataFrame)
        assert "Empty response received" in result.iloc[0]["summary"]

    @patch("lfx.components.data.web_search.requests.get")
    def test_perform_rss_read_invalid_xml(self, mock_get):
        """Test RSS read with invalid XML - returns empty DataFrame when no items found."""
        component = WebSearchComponent()
        component.query = "https://example.com/feed.rss"
        component.timeout = 5

        mock_response = Mock()
        mock_response.content = b"This is not valid XML"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = component.perform_rss_read()

        assert isinstance(result, DataFrame)
        # When no RSS items are found, it returns an empty DataFrame
        assert len(result) == 0

    def test_perform_rss_read_no_url(self):
        """Test RSS read with no URL provided."""
        component = WebSearchComponent()
        component.query = ""

        result = component.perform_rss_read()

        assert isinstance(result, DataFrame)
        assert "No RSS URL provided" in result.iloc[0]["summary"]

    @patch.object(WebSearchComponent, "perform_web_search")
    def test_perform_search_web_mode(self, mock_web_search):
        """Test perform_search routes to web search in Web mode."""
        component = WebSearchComponent()
        component.search_mode = "Web"

        mock_web_search.return_value = DataFrame(pd.DataFrame([{"result": "web"}]))

        result = component.perform_search()

        mock_web_search.assert_called_once()
        assert result.iloc[0]["result"] == "web"

    @patch.object(WebSearchComponent, "perform_news_search")
    def test_perform_search_news_mode(self, mock_news_search):
        """Test perform_search routes to news search in News mode."""
        component = WebSearchComponent()
        component.search_mode = "News"

        mock_news_search.return_value = DataFrame(pd.DataFrame([{"result": "news"}]))

        result = component.perform_search()

        mock_news_search.assert_called_once()
        assert result.iloc[0]["result"] == "news"

    @patch.object(WebSearchComponent, "perform_rss_read")
    def test_perform_search_rss_mode(self, mock_rss_read):
        """Test perform_search routes to RSS read in RSS mode."""
        component = WebSearchComponent()
        component.search_mode = "RSS"

        mock_rss_read.return_value = DataFrame(pd.DataFrame([{"result": "rss"}]))

        result = component.perform_search()

        mock_rss_read.assert_called_once()
        assert result.iloc[0]["result"] == "rss"

    @patch.object(WebSearchComponent, "perform_web_search")
    def test_perform_search_fallback(self, mock_web_search):
        """Test perform_search falls back to web search for unknown mode."""
        component = WebSearchComponent()
        component.search_mode = "UnknownMode"

        mock_web_search.return_value = DataFrame(pd.DataFrame([{"result": "fallback"}]))

        result = component.perform_search()

        mock_web_search.assert_called_once()
        assert result.iloc[0]["result"] == "fallback"

    def test_empty_query_error(self):
        """Test that empty query raises ValueError."""
        component = WebSearchComponent()
        component.query = ""
        component.timeout = 5

        with pytest.raises(ValueError, match="Empty search query"):
            component.perform_web_search()

    @patch("lfx.components.data.web_search.requests.get")
    def test_news_search_with_location(self, mock_get):
        """Test news search with location parameter."""
        component = WebSearchComponent()
        component.location = "San Francisco"
        component.timeout = 5

        # Mock RSS response
        mock_response = Mock()
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss>
            <channel>
                <item>
                    <title>Local News</title>
                    <link>https://local.example.com</link>
                    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
                    <description>San Francisco news</description>
                </item>
            </channel>
        </rss>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = component.perform_news_search()

        assert isinstance(result, DataFrame)
        # Check that the URL was constructed with location
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        assert "geo/San%20Francisco" in call_args or "geo/San+Francisco" in call_args
