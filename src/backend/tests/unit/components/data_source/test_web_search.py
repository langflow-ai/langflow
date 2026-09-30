from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest
from lfx.components.data_source.web_search import (
    DEFAULT_MAX_CONTENT_LENGTH,
    DEFAULT_MAX_RESULTS,
    TRUNCATION_SUFFIX,
    WebSearchComponent,
)
from lfx.schema import Data, DataFrame, Message
from lfx.utils.ssrf_protection import SSRFProtectionError
from pydantic import SecretStr, ValidationError

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

    @patch("lfx.components.data_source.web_search.is_ssrf_protection_enabled", return_value=True)
    @patch("lfx.components.data_source.web_search.create_ssrf_protected_sync_client")
    @patch("lfx.components.data_source.web_search.validate_and_resolve_url")
    def test_safe_get_url_validates_and_uses_dns_pinning(self, mock_validate, mock_create_client, mock_ssrf_enabled):
        """Arbitrary URL fetches must use the shared SSRF validation and DNS pinning path."""
        component = WebSearchComponent()
        component.timeout = 5
        mock_validate.return_value = ("https://example.com/feed.rss", ["93.184.216.34"])

        mock_response = Mock()
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_create_client.return_value = mock_client

        result = component._safe_get_url("example.com/feed.rss")

        assert result is mock_response
        mock_validate.assert_called_once_with("https://example.com/feed.rss")
        mock_ssrf_enabled.assert_called_once()
        mock_create_client.assert_called_once_with(hostname="example.com", validated_ips=["93.184.216.34"])
        mock_client.get.assert_called_once_with(
            "https://example.com/feed.rss", headers=None, timeout=5, follow_redirects=False
        )

    @patch("lfx.components.data_source.web_search.validate_and_resolve_url")
    def test_safe_get_url_blocks_ssrf_targets(self, mock_validate):
        """SSRF validation failures should be surfaced before any network fetch."""
        component = WebSearchComponent()
        component.timeout = 5
        mock_validate.side_effect = SSRFProtectionError("blocked")

        with pytest.raises(ValueError, match="SSRF Protection: blocked"):
            component._safe_get_url("http://169.254.169.254/latest/meta-data")

        mock_validate.assert_called_once_with("http://169.254.169.254/latest/meta-data")

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

    @patch.object(WebSearchComponent, "_safe_get_url")
    @patch("lfx.components.data_source.web_search.requests.get")
    def test_perform_web_search_success(self, mock_get, mock_safe_get):
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

        mock_get.return_value = mock_response
        mock_safe_get.return_value = mock_page_response

        result = component.perform_web_search()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["title"] == "Test Title"
        assert result.iloc[0]["snippet"] == "Test snippet content"
        assert "Page content" in result.iloc[0]["content"]

    @patch("lfx.components.data_source.web_search.requests.get")
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

    @patch("lfx.components.data_source.web_search.requests.get")
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

    @patch("lfx.components.data_source.web_search.requests.get")
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

    @patch("lfx.components.data_source.web_search.requests.get")
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

    @patch("lfx.components.data_source.web_search.requests.get")
    def test_perform_news_search_no_params(self, mock_get):  # noqa: ARG002
        """Test news search with no parameters."""
        component = WebSearchComponent()
        component.timeout = 5

        result = component.perform_news_search()

        assert isinstance(result, DataFrame)
        assert "No search parameters provided" in result.iloc[0]["summary"]

    @patch.object(WebSearchComponent, "_safe_get_url")
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

    @patch.object(WebSearchComponent, "_safe_get_url")
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

    @patch.object(WebSearchComponent, "_safe_get_url")
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

    def test_perform_rss_read_blocks_ssrf(self, monkeypatch):
        """Security: RSS mode must not fetch internal/metadata URLs when SSRF protection is on.

        The query is treated as a raw URL in RSS mode; a tenant could point it at the cloud
        metadata endpoint. With SSRF protection enabled the request must be blocked before any
        network call.
        """
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
        component = WebSearchComponent()
        component.query = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
        component.timeout = 5

        with patch("lfx.components.data_source.web_search.requests.get") as mock_get:
            result = component.perform_rss_read()

        mock_get.assert_not_called()
        assert isinstance(result, DataFrame)
        assert "SSRF Protection" in result.iloc[0]["summary"]

    def test_perform_web_search_blocks_ssrf_on_result_links(self, monkeypatch):
        """Security: result links resolving to internal IPs are not fetched when SSRF is on."""
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
        component = WebSearchComponent()
        component.query = "test query"
        component.timeout = 5

        mock_response = Mock()
        mock_response.text = (
            '<html><div class="result">'
            '<a class="result__a" href="?uddg=http%3A%2F%2F169.254.169.254%2Flatest%2Fmeta-data%2F">Title</a>'
            '<a class="result__snippet">snippet</a>'
            "</div></html>"
        )
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status.return_value = None

        with patch("lfx.components.data_source.web_search.requests.get") as mock_get:
            mock_get.return_value = mock_response
            result = component.perform_web_search()

        # Only the search-engine request fired; the internal result link was never fetched.
        assert mock_get.call_count == 1
        assert isinstance(result, DataFrame)
        assert "Blocked by SSRF protection" in result.iloc[0]["content"]

    @staticmethod
    def _serp_html(result_count: int) -> str:
        blocks = "".join(
            f'<div class="result">'
            f'<a class="result__a" href="?uddg=https%3A%2F%2Fexample.com%2F{i}">Title {i}</a>'
            f'<a class="result__snippet">Snippet {i}</a>'
            f"</div>"
            for i in range(result_count)
        )
        return f"<html>{blocks}</html>"

    @staticmethod
    def _serp_response(result_count: int) -> Mock:
        response = Mock()
        response.text = TestWebSearchComponent._serp_html(result_count)
        response.headers = {"content-type": "text/html"}
        response.raise_for_status.return_value = None
        return response

    @staticmethod
    def _page_response(body_length: int) -> Mock:
        response = Mock()
        response.text = f"<html><body>{'a' * body_length}</body></html>"
        response.raise_for_status.return_value = None
        return response

    @patch.object(WebSearchComponent, "_safe_get_url")
    @patch("lfx.components.data_source.web_search.requests.get")
    def test_should_cap_web_results_when_max_results_is_set(self, mock_get, mock_safe_get):
        """Regression (LE-2164): the scrape loop must stop at max_results."""
        component = WebSearchComponent()
        component.query = "test query"
        component.timeout = 5
        component.max_results = 3

        mock_get.return_value = self._serp_response(result_count=12)
        mock_safe_get.return_value = self._page_response(body_length=50)

        result = component.perform_web_search()

        assert len(result) == 3
        assert mock_safe_get.call_count == 3

    @patch.object(WebSearchComponent, "_safe_get_url")
    @patch("lfx.components.data_source.web_search.requests.get")
    def test_should_truncate_content_when_max_content_length_is_set(self, mock_get, mock_safe_get):
        """Regression (LE-2164): scraped page text must never exceed max_content_length."""
        component = WebSearchComponent()
        component.query = "test query"
        component.timeout = 5
        component.max_content_length = 500

        mock_get.return_value = self._serp_response(result_count=1)
        mock_safe_get.return_value = self._page_response(body_length=40_000)

        result = component.perform_web_search()

        content = result.iloc[0]["content"]
        assert len(content) <= 500
        assert content.endswith("... [truncated]")

    @pytest.mark.parametrize("limit", range(1, len(TRUNCATION_SUFFIX)))
    def test_should_mark_truncated_content_when_limit_is_shorter_than_suffix(self, limit):
        """Every positive content limit must retain a recognizable truncation marker."""
        component = WebSearchComponent()

        content = component._truncate_content("a" * 100, limit)

        assert len(content) == limit
        assert content.endswith("…")

    def test_should_use_full_truncation_marker_at_suffix_length(self):
        """The full marker fits exactly at its existing length boundary."""
        component = WebSearchComponent()

        content = component._truncate_content("a" * 100, len(TRUNCATION_SUFFIX))

        assert content == TRUNCATION_SUFFIX
        assert component._truncate_content("a" * 100, len(TRUNCATION_SUFFIX) + 1) == f"a{TRUNCATION_SUFFIX}"
        assert component._truncate_content("a" * len(TRUNCATION_SUFFIX), len(TRUNCATION_SUFFIX)) == "a" * len(
            TRUNCATION_SUFFIX
        )

    @patch.object(WebSearchComponent, "_safe_get_url")
    @patch("lfx.components.data_source.web_search.requests.get")
    def test_should_bound_payload_when_limits_are_absent(self, mock_get, mock_safe_get):
        """Saved flows frozen before LE-2164 carry no limit fields; defaults must still bound them."""
        component = WebSearchComponent()
        component.query = "Sample Slide Show"
        component.timeout = 5

        mock_get.return_value = self._serp_response(result_count=10)
        mock_safe_get.return_value = self._page_response(body_length=40_755)

        result = component.perform_web_search()

        total_chars = sum(len(str(value)) for row in result.to_dict(orient="records") for value in row.values())
        assert len(result) == 5
        assert all(len(row["content"]) <= 2000 for row in result.to_dict(orient="records"))
        assert total_chars < 20_000

    @patch.object(WebSearchComponent, "_safe_get_url")
    @patch("lfx.components.data_source.web_search.requests.get")
    def test_should_keep_full_payload_when_limits_are_disabled(self, mock_get, mock_safe_get):
        """Zero is the documented opt-out for both limits."""
        component = WebSearchComponent()
        component.query = "test query"
        component.timeout = 5
        component.set_attributes({"max_results": 0, "max_content_length": 0})

        mock_get.return_value = self._serp_response(result_count=12)
        mock_safe_get.return_value = self._page_response(body_length=10_000)

        result = component.perform_web_search()

        assert len(result) == 12
        assert len(result.iloc[0]["content"]) == 10_000

    @patch("lfx.components.data_source.web_search.requests.get")
    def test_should_cap_news_results_when_max_results_is_set(self, mock_get):
        """Regression (LE-2164): News mode also feeds the agent context and must be bounded."""
        component = WebSearchComponent()
        component.query = "test news"
        component.timeout = 5
        component.max_results = 4

        items = "".join(
            f"<item><title>News {i}</title><link>https://news.example.com/{i}</link>"
            f"<pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate><description>Body {i}</description></item>"
            for i in range(30)
        )
        mock_response = Mock()
        mock_response.content = f'<?xml version="1.0" encoding="UTF-8"?><rss><channel>{items}</channel></rss>'.encode()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = component.perform_news_search()

        assert len(result) == 4

    @patch("lfx.components.data_source.web_search.requests.get")
    def test_should_bound_news_text_fields(self, mock_get):
        """Every text field in a News item must honor max_content_length."""
        component = WebSearchComponent()
        component.query = "test news"
        component.timeout = 5
        component.max_results = 1
        component.max_content_length = 100

        oversized = "a" * 100_000
        mock_response = Mock()
        mock_response.content = (
            '<?xml version="1.0" encoding="UTF-8"?><rss><channel><item>'
            f"<title>{oversized}</title><link>https://example.com/{oversized}</link>"
            f"<pubDate>{oversized}</pubDate><description>{oversized}</description>"
            "</item></channel></rss>"
        ).encode()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = component.perform_news_search()

        row = result.iloc[0]
        for field in ("title", "link", "published", "summary"):
            assert len(row[field]) == 100
            assert row[field].endswith(TRUNCATION_SUFFIX)

    @patch.object(WebSearchComponent, "_safe_get_url")
    def test_should_cap_rss_items_when_max_results_is_set(self, mock_get):
        """Regression (LE-2164): RSS mode must honour the same cap."""
        component = WebSearchComponent()
        component.query = "https://example.com/feed.rss"
        component.timeout = 5
        component.max_results = 2

        items = "".join(
            f"<item><title>Item {i}</title><link>https://example.com/{i}</link>"
            f"<pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate><description>Body {i}</description></item>"
            for i in range(10)
        )
        mock_response = Mock()
        mock_response.content = f'<?xml version="1.0" encoding="UTF-8"?><rss><channel>{items}</channel></rss>'.encode()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = component.perform_rss_read()

        assert len(result) == 2

    @patch.object(WebSearchComponent, "_safe_get_url")
    def test_should_bound_rss_text_fields(self, mock_get):
        """A single oversized RSS item must not flood the caller's context window."""
        component = WebSearchComponent()
        component.query = "https://example.com/feed.rss"
        component.timeout = 5
        component.max_results = 1
        component.max_content_length = 100

        oversized = "a" * 100_000
        mock_response = Mock()
        mock_response.content = (
            '<?xml version="1.0" encoding="UTF-8"?><rss><channel><item>'
            f"<title>{oversized}</title><link>https://example.com/{oversized}</link>"
            f"<pubDate>{oversized}</pubDate><description>{oversized}</description>"
            "</item></channel></rss>"
        ).encode()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = component.perform_rss_read()

        assert len(result) == 1
        row = result.iloc[0]
        fields = ("title", "link", "published", "summary")
        for field in fields:
            assert len(row[field]) == 100
            assert row[field].endswith(TRUNCATION_SUFFIX)
        assert sum(len(row[field]) for field in fields) <= 4 * 100

    @pytest.mark.parametrize(
        ("name", "default"), [("max_results", DEFAULT_MAX_RESULTS), ("max_content_length", DEFAULT_MAX_CONTENT_LENGTH)]
    )
    @pytest.mark.parametrize("invalid", [None, "", "not-a-number", -1, -0.5, 0.5, False, True, float("inf"), "1e309"])
    def test_should_normalize_invalid_limits_before_input_validation(self, name, default, invalid):
        """Graph input binding must fall back safely instead of disabling or rejecting limits."""
        component = WebSearchComponent()

        component.set_attributes({name: invalid})

        assert component._get_limit(name, default) == default

    @pytest.mark.parametrize("zero", [0, 0.0, "0"])
    def test_should_only_disable_limits_for_explicit_zero(self, zero):
        """Numeric zero remains the sole supported opt-out after normal input binding."""
        component = WebSearchComponent()

        component.set_attributes({"max_results": zero})

        assert component._get_limit("max_results", DEFAULT_MAX_RESULTS) is None

    @pytest.mark.parametrize("wrapped", [Message(text="2"), Data(text="2")])
    def test_should_preserve_wrapped_integer_limits(self, wrapped):
        """Component-specific normalization must preserve IntInput's Message/Data support."""
        component = WebSearchComponent()

        component.set_attributes({"max_results": wrapped})

        assert component._get_limit("max_results", DEFAULT_MAX_RESULTS) == 2

    @pytest.mark.parametrize("name", ["max_results", "max_content_length"])
    def test_should_reject_credential_variables_for_limits(self, name):
        """Pre-normalization must preserve the global non-password credential guard."""
        component = WebSearchComponent()
        raw_secret = "credential-sentinel"  # noqa: S105  # pragma: allowlist secret

        with pytest.raises(ValidationError) as excinfo:
            component.set_attributes({name: SecretStr(raw_secret)})

        error_text = str(excinfo.value)
        assert "Credential-typed global variable" in error_text
        assert name in error_text
        assert raw_secret not in error_text

    @patch.object(WebSearchComponent, "_safe_get_url")
    @patch("lfx.components.data_source.web_search.requests.get")
    def test_should_fall_back_to_defaults_when_limits_are_invalid(self, mock_get, mock_safe_get):
        """Tool-mode callers can pass strings/None; invalid limits must not crash the search."""
        component = WebSearchComponent()
        component.query = "test query"
        component.timeout = 5
        component.set_attributes({"max_results": "not-a-number", "max_content_length": None})

        mock_get.return_value = self._serp_response(result_count=12)
        mock_safe_get.return_value = self._page_response(body_length=40_000)

        result = component.perform_web_search()

        assert len(result) == 5
        assert len(result.iloc[0]["content"]) <= 2000

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

    @patch("lfx.components.data_source.web_search.requests.get")
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
