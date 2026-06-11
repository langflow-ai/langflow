import ipaddress
import os
import socket
from unittest.mock import Mock, patch

import pytest
import requests
from lfx.components.data_source.rss import RSSReaderComponent
from lfx.schema import DataFrame

from tests.base import ComponentTestBaseWithoutClient


def _resolve_public(host, *_args, **_kwargs):
    """socket.getaddrinfo stub: hostnames resolve to a public IP, literal IPs to themselves."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        ip = "93.184.216.34"  # hostname -> public IP
    else:
        ip = host  # literal IP -> itself
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, "", (ip, 0))]


_VALID_RSS = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<rss version="2.0"><channel>'
    b"<item><title>A</title><link>https://example.com/a</link>"
    b"<pubDate>2024-03-20</pubDate><description>summary</description></item>"
    b"</channel></rss>"
)


def _mock_response(status_code=200, *, location=None, content=b""):
    """Build a minimal mock ``requests.Response``."""
    response = Mock()
    response.status_code = status_code
    response.headers = {"Location": location} if location else {}
    response.content = content
    response.raise_for_status = Mock()
    return response


class TestRSSReaderComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def _disable_ssrf_for_parsing_tests(self):
        """Isolate the parsing-focused tests from SSRF validation and DNS resolution.

        SSRF behavior is covered separately in ``TestRSSReaderSSRFProtection``.
        """
        with patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "false"}):
            yield

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return RSSReaderComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "rss_url": "https://example.com/feed.xml",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    def test_successful_rss_fetch(self):
        # Mock RSS feed content
        mock_rss_content = """
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test Article 1</title>
                    <link>https://example.com/1</link>
                    <pubDate>2024-03-20</pubDate>
                    <description>Test summary 1</description>
                </item>
                <item>
                    <title>Test Article 2</title>
                    <link>https://example.com/2</link>
                    <pubDate>2024-03-21</pubDate>
                    <description>Test summary 2</description>
                </item>
            </channel>
        </rss>
        """

        # Mock the requests.get response
        mock_response = Mock()
        mock_response.content = mock_rss_content.encode("utf-8")
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            component = RSSReaderComponent(rss_url="https://example.com/feed.xml")
            result = component.read_rss()

            assert isinstance(result, DataFrame)
            assert len(result) == 2
            assert list(result.columns) == ["title", "link", "published", "summary"]
            assert result.iloc[0]["title"] == "Test Article 1"
            assert result.iloc[1]["title"] == "Test Article 2"

    def test_rss_fetch_with_missing_fields(self):
        # Mock RSS feed content with missing fields
        mock_rss_content = """
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test Article</title>
                    <!-- Missing link -->
                    <pubDate>2024-03-20</pubDate>
                    <!-- Missing description -->
                </item>
            </channel>
        </rss>
        """

        mock_response = Mock()
        mock_response.content = mock_rss_content.encode("utf-8")
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            component = RSSReaderComponent(rss_url="https://example.com/feed.xml")
            result = component.read_rss()

            assert isinstance(result, DataFrame)
            assert len(result) == 1
            assert result.iloc[0]["title"] == "Test Article"
            assert result.iloc[0]["link"] == ""
            assert result.iloc[0]["summary"] == ""

    def test_rss_fetch_error(self):
        # Mock a failed request
        with patch("requests.get", side_effect=requests.RequestException("Network error")):
            component = RSSReaderComponent(rss_url="https://example.com/feed.xml")
            result = component.read_rss()

            assert isinstance(result, DataFrame)
            assert len(result) == 1
            assert result.iloc[0]["title"] == "Error"
            assert result.iloc[0]["link"] == ""
            assert result.iloc[0]["published"] == ""
            assert "Network error" in result.iloc[0]["summary"]

    def test_empty_rss_feed(self):
        # Mock empty RSS feed
        mock_rss_content = """
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
            </channel>
        </rss>
        """

        mock_response = Mock()
        mock_response.content = mock_rss_content.encode("utf-8")
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            component = RSSReaderComponent(rss_url="https://example.com/feed.xml")
            result = component.read_rss()

            assert isinstance(result, DataFrame)
            assert len(result) == 0
            assert list(result.columns) == ["title", "link", "published", "summary"]


class TestRSSReaderSSRFProtection:
    """Regression tests for the SSRF bypass via the legacy RSS Reader component.

    With SSRF protection enabled, the user-supplied feed URL (and any redirect it
    follows) must not be able to reach internal services such as the cloud metadata
    endpoint, loopback, or private networks.
    """

    def test_blocks_cloud_metadata_endpoint(self):
        """The cloud metadata endpoint is blocked; no request is made."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("requests.get") as mock_get,
        ):
            component = RSSReaderComponent(rss_url="http://169.254.169.254/latest/meta-data/iam/security-credentials/")
            result = component.read_rss()

        assert isinstance(result, DataFrame)
        assert result.iloc[0]["title"] == "Error"
        assert "blocked" in result.iloc[0]["summary"].lower() or "ssrf" in result.iloc[0]["summary"].lower()
        mock_get.assert_not_called()

    def test_blocks_localhost(self):
        """A loopback feed URL is blocked; no request is made."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("requests.get") as mock_get,
        ):
            component = RSSReaderComponent(rss_url="http://127.0.0.1:8080/feed.xml")
            result = component.read_rss()

        assert result.iloc[0]["title"] == "Error"
        mock_get.assert_not_called()

    def test_blocks_private_network(self):
        """An RFC1918 feed URL is blocked; no request is made."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("requests.get") as mock_get,
        ):
            component = RSSReaderComponent(rss_url="http://192.168.1.1/feed.xml")
            result = component.read_rss()

        assert result.iloc[0]["title"] == "Error"
        mock_get.assert_not_called()

    def test_blocks_redirect_to_metadata(self):
        """A public feed that redirects to the metadata endpoint is blocked at the redirect hop."""
        redirect = _mock_response(302, location="http://169.254.169.254/latest/meta-data/")

        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch("requests.get", return_value=redirect) as mock_get,
        ):
            component = RSSReaderComponent(rss_url="http://public-feed.example.com/rss")
            result = component.read_rss()

        assert result.iloc[0]["title"] == "Error"
        # Only the first (public) hop was requested; the internal redirect was not followed.
        assert mock_get.call_count == 1

    def test_allows_public_feed(self):
        """A legitimate public RSS feed is fetched and parsed with SSRF protection enabled."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch("requests.get", return_value=_mock_response(200, content=_VALID_RSS)),
        ):
            component = RSSReaderComponent(rss_url="http://feed.example.com/rss")
            result = component.read_rss()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["title"] == "A"

    def test_protection_disabled_allows_internal(self):
        """With SSRF protection disabled, internal URLs are reachable (user opted out)."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "false"}),
            patch("requests.get", return_value=_mock_response(200, content=_VALID_RSS)) as mock_get,
        ):
            component = RSSReaderComponent(rss_url="http://127.0.0.1:8080/feed.xml")
            result = component.read_rss()

        assert len(result) == 1
        assert result.iloc[0]["title"] == "A"
        mock_get.assert_called_once()
