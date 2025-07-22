from unittest.mock import Mock, patch

import pytest
import requests

from lfx.components.data.news_search import NewsSearchComponent
from lfx.schema import DataFrame
from tests.base import ComponentTestBaseWithoutClient


class TestNewsSearchComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return NewsSearchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"query": "OpenAI"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_successful_news_search(self):
        # Mock Google News RSS feed content
        mock_rss_content = """
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test News 1</title>
                    <link>https://example.com/1</link>
                    <pubDate>2024-03-20</pubDate>
                    <description>Summary 1</description>
                </item>
                <item>
                    <title>Test News 2</title>
                    <link>https://example.com/2</link>
                    <pubDate>2024-03-21</pubDate>
                    <description>Summary 2</description>
                </item>
            </channel>
        </rss>
        """
        mock_response = Mock()
        mock_response.content = mock_rss_content.encode("utf-8")
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            component = NewsSearchComponent(query="OpenAI")
            result = component.search_news()
            assert isinstance(result, DataFrame)
            news_results_df = result
            assert len(news_results_df) == 2
            assert list(news_results_df.columns) == ["title", "link", "published", "summary"]
            assert news_results_df.iloc[0]["title"] == "Test News 1"
            assert news_results_df.iloc[1]["title"] == "Test News 2"

    def test_news_search_error(self):
        with patch("requests.get", side_effect=requests.RequestException("Network error")):
            component = NewsSearchComponent(query="OpenAI")
            result = component.search_news()
            assert isinstance(result, DataFrame)
            news_results_df = result
            assert len(news_results_df) == 1
            assert news_results_df.iloc[0]["title"] == "Error"
            assert "Network error" in news_results_df.iloc[0]["summary"]

    def test_empty_news_results(self):
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
            component = NewsSearchComponent(query="OpenAI")
            result = component.search_news()
            assert isinstance(result, DataFrame)
            news_results_df = result
            assert len(news_results_df) == 1
            assert news_results_df.iloc[0]["title"] == "No articles found"
