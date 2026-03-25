from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx.components.youdotcom.youdotcom_contents import YouDotComContentsComponent

from tests.base import ComponentTestBaseWithoutClient


class TestYouDotComContentsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return YouDotComContentsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-ydc-key",
            "urls": "https://example.com",
            "formats": "markdown",
            "crawl_timeout": 10,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_basic_setup(self, component_class, default_kwargs):
        component = component_class()
        component.set_attributes(default_kwargs)

        assert component.display_name == "You.com Contents"
        assert component.icon == "YouDotCom"
        assert component.api_key == "test-ydc-key"
        assert component.urls == "https://example.com"
        assert component.formats == "markdown"

    @patch("lfx.components.youdotcom.youdotcom_contents.httpx.Client")
    def test_fetch_content_success(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "url": "https://example.com",
                "title": "Example Page",
                "markdown": "# Hello World\n\nThis is example content.",
            },
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "Hello World" in results[0].text
        assert results[0].data["url"] == "https://example.com"
        assert results[0].data["title"] == "Example Page"

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["headers"]["User-Agent"] == "langflow-youdotcom/1.0"
        assert call_kwargs[1]["headers"]["X-API-Key"] == "test-ydc-key"

        payload = call_kwargs[1]["json"]
        assert payload["urls"] == ["https://example.com"]
        assert payload["formats"] == ["markdown"]

    @patch("lfx.components.youdotcom.youdotcom_contents.httpx.Client")
    def test_fetch_content_multiple_urls(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"url": "https://example.com", "title": "Page 1", "markdown": "Content 1"},
            {"url": "https://example.org", "title": "Page 2", "markdown": "Content 2"},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        default_kwargs["urls"] = "https://example.com, https://example.org"
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 2

        payload = mock_client.post.call_args[1]["json"]
        assert payload["urls"] == ["https://example.com", "https://example.org"]

    @patch("lfx.components.youdotcom.youdotcom_contents.httpx.Client")
    def test_fetch_content_html_format(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"url": "https://example.com", "title": "Page", "html": "<h1>Hello</h1>"},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        default_kwargs["formats"] = "html"
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "<h1>Hello</h1>" in results[0].text

    @patch("lfx.components.youdotcom.youdotcom_contents.httpx.Client")
    def test_fetch_content_metadata_format(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "url": "https://example.com",
                "title": "Page",
                "metadata": {"site_name": "Example", "favicon_url": "https://example.com/favicon.ico"},
            },
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        default_kwargs["formats"] = "metadata"
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert results[0].data["metadata"]["site_name"] == "Example"

    @patch("lfx.components.youdotcom.youdotcom_contents.httpx.Client")
    def test_fetch_content_timeout(self, mock_client_class, component_class, default_kwargs):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("timed out")
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "timed out" in results[0].text.lower()
        assert "error" in results[0].data

    @patch("lfx.components.youdotcom.youdotcom_contents.httpx.Client")
    def test_fetch_content_http_error(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = "Validation Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "422", request=MagicMock(), response=mock_response
        )

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "422" in results[0].text
        assert "error" in results[0].data

    def test_empty_urls_returns_error(self, component_class, default_kwargs):
        """Test that empty URLs returns validation error."""
        default_kwargs["urls"] = ""
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "urls cannot be empty" in results[0].text.lower()

    def test_whitespace_only_urls_returns_error(self, component_class, default_kwargs):
        """Test that whitespace-only URLs returns validation error."""
        default_kwargs["urls"] = "   ,   ,   "
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "urls cannot be empty" in results[0].text.lower()

    def test_crawl_timeout_below_min_returns_error(self, component_class, default_kwargs):
        """Test that crawl_timeout=0 returns validation error."""
        default_kwargs["crawl_timeout"] = 0
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "crawl_timeout must be between 1 and 60" in results[0].text

    def test_crawl_timeout_above_max_returns_error(self, component_class, default_kwargs):
        """Test that crawl_timeout=61 returns validation error."""
        default_kwargs["crawl_timeout"] = 61
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "crawl_timeout must be between 1 and 60" in results[0].text

    @patch("lfx.components.youdotcom.youdotcom_contents.httpx.Client")
    def test_fetch_content_dataframe_structure(self, mock_client_class, component_class, default_kwargs):
        """Test DataFrame has correct structure with expected columns."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "url": "https://example.com",
                "title": "Example Page",
                "markdown": "# Hello World",
            },
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        df = component.fetch_content_dataframe()

        assert df is not None
        assert len(df) == 1
        assert "url" in df.columns
        assert "title" in df.columns
        assert "content" in df.columns
        assert df.iloc[0]["url"] == "https://example.com"
        assert df.iloc[0]["title"] == "Example Page"
