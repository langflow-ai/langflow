from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx.components.youdotcom.youdotcom_search import YouDotComSearchComponent

from tests.base import ComponentTestBaseWithoutClient


class TestYouDotComSearchComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return YouDotComSearchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-ydc-key",
            "query": "test query",
            "max_results": 5,
            "country": None,
            "safesearch": "moderate",
            "freshness": None,
            "livecrawl": None,
            "livecrawl_formats": None,
            "language": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_basic_setup(self, component_class, default_kwargs):
        component = component_class()
        component.set_attributes(default_kwargs)

        assert component.display_name == "You.com Search"
        assert component.icon == "YouDotCom"
        assert component.api_key == "test-ydc-key"
        assert component.query == "test query"
        assert component.max_results == 5

    @patch("lfx.components.youdotcom.youdotcom_search.httpx.Client")
    def test_fetch_content_success(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": {
                "web": [
                    {
                        "title": "Test Result",
                        "url": "https://example.com",
                        "description": "A test result description",
                        "snippets": ["snippet 1"],
                    },
                    {
                        "title": "Second Result",
                        "url": "https://example.org",
                        "description": "Another description",
                        "snippets": ["snippet 2"],
                    },
                ],
            },
            "metadata": {"search_uuid": "abc-123", "query": "test query", "latency": 0.5},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 2
        assert results[0].text == "A test result description"
        assert results[0].data["title"] == "Test Result"
        assert results[0].data["url"] == "https://example.com"
        assert results[1].data["title"] == "Second Result"

        call_kwargs = mock_client.get.call_args
        assert call_kwargs[1]["headers"]["User-Agent"] == "langflow-youdotcom/1.0"
        assert call_kwargs[1]["headers"]["X-API-Key"] == "test-ydc-key"
        assert call_kwargs[1]["params"]["query"] == "test query"
        assert call_kwargs[1]["params"]["count"] == 5

    @patch("lfx.components.youdotcom.youdotcom_search.httpx.Client")
    def test_fetch_content_with_news(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": {
                "web": [],
                "news": [
                    {
                        "title": "News Item",
                        "url": "https://news.example.com",
                        "description": "Breaking news",
                        "page_age": "2024-01-01T00:00:00Z",
                    },
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert results[0].data["title"] == "News Item"
        assert results[0].data["page_age"] == "2024-01-01T00:00:00Z"

    @patch("lfx.components.youdotcom.youdotcom_search.httpx.Client")
    def test_fetch_content_sends_optional_params(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": {"web": []}}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        default_kwargs["country"] = "US"
        default_kwargs["freshness"] = "week"
        default_kwargs["livecrawl"] = "web"
        default_kwargs["livecrawl_formats"] = "markdown"
        default_kwargs["language"] = "EN"

        component = component_class()
        component.set_attributes(default_kwargs)
        component.fetch_content()

        params = mock_client.get.call_args[1]["params"]
        assert params["country"] == "US"
        assert params["freshness"] == "week"
        assert params["livecrawl"] == "web"
        assert params["livecrawl_formats"] == "markdown"
        assert params["language"] == "EN"

    @patch("lfx.components.youdotcom.youdotcom_search.httpx.Client")
    def test_fetch_content_timeout(self, mock_client_class, component_class, default_kwargs):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.TimeoutException("timed out")
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "timed out" in results[0].text.lower()
        assert "error" in results[0].data

    @patch("lfx.components.youdotcom.youdotcom_search.httpx.Client")
    def test_fetch_content_http_error(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "401" in results[0].text
        assert "error" in results[0].data

    @patch("lfx.components.youdotcom.youdotcom_search.httpx.Client")
    def test_fetch_content_dataframe(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": {
                "web": [
                    {
                        "title": "Test",
                        "url": "https://example.com",
                        "description": "desc",
                        "snippets": [],
                    },
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        df = component.fetch_content_dataframe()

        assert df is not None
        assert len(df) == 1

    @patch("lfx.components.youdotcom.youdotcom_search.httpx.Client")
    def test_max_results_boundary_min_valid(self, mock_client_class, component_class, default_kwargs):
        """Test max_results=1 is valid (boundary at lower end)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": {"web": []}}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        default_kwargs["max_results"] = 1
        component = component_class()
        component.set_attributes(default_kwargs)
        component.fetch_content()

        params = mock_client.get.call_args[1]["params"]
        assert params["count"] == 1

    @patch("lfx.components.youdotcom.youdotcom_search.httpx.Client")
    def test_max_results_boundary_max_valid(self, mock_client_class, component_class, default_kwargs):
        """Test max_results=100 is valid (boundary at upper end)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": {"web": []}}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        default_kwargs["max_results"] = 100
        component = component_class()
        component.set_attributes(default_kwargs)
        component.fetch_content()

        params = mock_client.get.call_args[1]["params"]
        assert params["count"] == 100

    def test_max_results_below_min_returns_error(self, component_class, default_kwargs):
        """Test max_results=0 returns validation error."""
        default_kwargs["max_results"] = 0
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "max_results must be between 1 and 100" in results[0].text

    def test_max_results_above_max_returns_error(self, component_class, default_kwargs):
        """Test max_results=101 returns validation error."""
        default_kwargs["max_results"] = 101
        component = component_class()
        component.set_attributes(default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "max_results must be between 1 and 100" in results[0].text

    @patch("lfx.components.youdotcom.youdotcom_search.httpx.Client")
    def test_fetch_content_dataframe_structure(self, mock_client_class, component_class, default_kwargs):
        """Test DataFrame has correct structure with expected columns."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": {
                "web": [
                    {
                        "title": "Test Result",
                        "url": "https://example.com",
                        "description": "A test result description",
                        "snippets": ["snippet 1"],
                    },
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        df = component.fetch_content_dataframe()

        assert df is not None
        assert len(df) == 1
        assert "title" in df.columns
        assert "url" in df.columns
        assert "description" in df.columns
        assert "snippets" in df.columns
        assert df.iloc[0]["title"] == "Test Result"
        assert df.iloc[0]["url"] == "https://example.com"
