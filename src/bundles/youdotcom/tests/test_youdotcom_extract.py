from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_youdotcom.components.youdotcom.youdotcom_extract import YouDotComExtractComponent


def _mock_client(mock_client_class, response):
    mock_response = MagicMock()
    mock_response.json.return_value = response
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_class.return_value = mock_client
    return mock_client


class TestYouDotComExtractComponent:
    @pytest.fixture
    def component_class(self):
        return YouDotComExtractComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-ydc-key",
            "urls": "https://example.com",
            "formats": "markdown",
            "timeout": 30,
        }

    def test_basic_setup(self, component_class, default_kwargs):
        component = component_class()
        component.set_attributes(default_kwargs)

        assert component.display_name == "You.com Extract"
        assert component.icon == "YouDotCom"
        assert component.api_key == "test-ydc-key"
        assert component.urls == "https://example.com"
        assert component.formats == "markdown"

    @patch("lfx_youdotcom.components.youdotcom.youdotcom_extract.httpx.Client")
    def test_fetch_content_success(self, mock_client_class, component_class, default_kwargs):
        mock_client = _mock_client(
            mock_client_class,
            {
                "url": "https://example.com",
                "title": "Example Page",
                "contents": {"full_page": {"markdown": "# Hello World\n\nThis is example content."}},
            },
        )
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
        assert call_kwargs[0][0] == "https://ydc-index.io/v1/extract"
        assert call_kwargs[1]["json"] == {
            "url": "https://example.com",
            "full_page": {"extraction_formats": ["markdown"]},
            "timeout": 30,
        }

    @patch("lfx_youdotcom.components.youdotcom.youdotcom_extract.httpx.Client")
    def test_fetch_content_multiple_urls(self, mock_client_class, component_class, default_kwargs):
        mock_client = _mock_client(
            mock_client_class,
            {
                "url": "https://example.com",
                "title": "Example Page",
                "contents": {"full_page": {"markdown": "Content"}},
            },
        )
        default_kwargs["urls"] = "https://example.com\nhttps://example.org"
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 2
        assert mock_client.post.call_count == 2
        assert mock_client.post.call_args_list[0][1]["json"]["url"] == "https://example.com"
        assert mock_client.post.call_args_list[1][1]["json"]["url"] == "https://example.org"

    @patch("lfx_youdotcom.components.youdotcom.youdotcom_extract.httpx.Client")
    def test_fetch_content_html_and_metadata(self, mock_client_class, component_class, default_kwargs):
        mock_client = _mock_client(
            mock_client_class,
            {
                "url": "https://example.com",
                "title": "Page",
                "contents": {"full_page": {"html": "<h1>Hello</h1>"}},
                "metadata": {"site_name": "Example", "favicon_url": "https://example.com/favicon.ico"},
            },
        )
        default_kwargs["formats"] = "html"
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert results[0].text == "<h1>Hello</h1>"
        assert results[0].data["metadata"]["site_name"] == "Example"
        assert mock_client.post.call_args[1]["json"]["full_page"] == {"extraction_formats": ["html"]}

    @patch("lfx_youdotcom.components.youdotcom.youdotcom_extract.httpx.Client")
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

    @patch("lfx_youdotcom.components.youdotcom.youdotcom_extract.httpx.Client")
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

    @pytest.mark.parametrize("urls", ["", "   \n   \n   "])
    def test_blank_urls_return_error(self, urls, component_class, default_kwargs):
        default_kwargs["urls"] = urls
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "urls cannot be empty" in results[0].text.lower()

    @pytest.mark.parametrize("timeout", [1, 101])
    def test_timeout_outside_range_returns_error(self, timeout, component_class, default_kwargs):
        default_kwargs["timeout"] = timeout
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "timeout must be between 2 and 100" in results[0].text

    @patch("lfx_youdotcom.components.youdotcom.youdotcom_extract.httpx.Client")
    def test_fetch_content_dataframe_structure(self, mock_client_class, component_class, default_kwargs):
        _mock_client(
            mock_client_class,
            {
                "url": "https://example.com",
                "title": "Example Page",
                "contents": {"full_page": {"markdown": "# Hello World"}},
            },
        )
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
