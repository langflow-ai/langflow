from unittest.mock import Mock, patch

import pytest
import requests
from langflow.components.data.rss import RSSReaderComponent
from langflow.schema import DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestRSSReaderComponent(ComponentTestBaseWithoutClient):
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
