from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx.components.perplexity.perplexity_search import PerplexitySearchComponent
from lfx.schema import Data, DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestPerplexitySearchComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return PerplexitySearchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-key",
            "query": "what is langflow",
            "max_results": 3,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @pytest.fixture
    def fake_search_response(self):
        return {
            "results": [
                {
                    "title": "Result One",
                    "url": "https://example.com/one",
                    "snippet": "First snippet.",
                    "date": "2025-01-01",
                    "last_updated": "2025-01-02",
                },
                {
                    "title": "Result Two",
                    "url": "https://example.com/two",
                    "snippet": "Second snippet.",
                    "date": "2025-02-01",
                    "last_updated": "2025-02-02",
                },
            ],
            "id": "abc",
            "server_time": "2025-03-01T00:00:00Z",
        }

    def test_component_initialization(self, component_class):
        component = component_class()
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]

        assert node_data["display_name"] == "Perplexity Search API"
        assert node_data["icon"] == "Perplexity"
        template = node_data["template"]
        for input_name in ("api_key", "query", "max_results", "search_recency_filter", "country", "search_mode"):
            assert input_name in template

    @patch("lfx.components.perplexity.perplexity_search.httpx.Client")
    def test_fetch_content_success(self, mock_client_cls, component_class, default_kwargs, fake_search_response):
        mock_response = MagicMock()
        mock_response.json.return_value = fake_search_response
        mock_response.raise_for_status.return_value = None
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        component = component_class(**default_kwargs)
        results = component.fetch_content()

        assert isinstance(results, list)
        assert len(results) == 2
        assert isinstance(results[0], Data)
        assert results[0].data["title"] == "Result One"
        assert results[0].data["url"] == "https://example.com/one"
        assert results[0].text == "First snippet."

        # Verify the request was sent with the correct attribution header and payload.
        call_args = mock_client.post.call_args
        assert call_args.args[0] == "https://api.perplexity.ai/search"
        sent_headers = call_args.kwargs["headers"]
        assert sent_headers["Authorization"] == "Bearer test-key"
        assert sent_headers["Content-Type"] == "application/json"
        assert "X-Pplx-Integration" in sent_headers
        assert sent_headers["X-Pplx-Integration"].startswith("langflow/")
        sent_payload = call_args.kwargs["json"]
        assert sent_payload == {"query": "what is langflow", "max_results": 3}

    @patch("lfx.components.perplexity.perplexity_search.httpx.Client")
    def test_fetch_content_optional_filters(self, mock_client_cls, component_class, fake_search_response):
        mock_response = MagicMock()
        mock_response.json.return_value = fake_search_response
        mock_response.raise_for_status.return_value = None
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        component = component_class(
            api_key="test-key",
            query="langflow",
            max_results=10,
            search_recency_filter="week",
            country="US",
            search_mode="academic",
        )
        component.fetch_content()

        sent_payload = mock_client.post.call_args.kwargs["json"]
        assert sent_payload["query"] == "langflow"
        assert sent_payload["max_results"] == 10
        assert sent_payload["search_recency_filter"] == "week"
        assert sent_payload["country"] == "US"
        assert sent_payload["search_mode"] == "academic"

    @patch("lfx.components.perplexity.perplexity_search.httpx.Client")
    def test_max_results_clamped(self, mock_client_cls, component_class, fake_search_response):
        mock_response = MagicMock()
        mock_response.json.return_value = fake_search_response
        mock_response.raise_for_status.return_value = None
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        component = component_class(api_key="test-key", query="langflow", max_results=999)
        component.fetch_content()

        sent_payload = mock_client.post.call_args.kwargs["json"]
        assert sent_payload["max_results"] == 20

    @patch("lfx.components.perplexity.perplexity_search.httpx.Client")
    def test_malformed_max_results_defaults_to_five(self, mock_client_cls, component_class, fake_search_response):
        mock_response = MagicMock()
        mock_response.json.return_value = fake_search_response
        mock_response.raise_for_status.return_value = None
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        component = component_class(api_key="test-key", query="langflow", max_results="many")
        component.fetch_content()

        sent_payload = mock_client.post.call_args.kwargs["json"]
        assert sent_payload["max_results"] == 5

    def test_missing_query_returns_error(self, component_class):
        component = component_class(api_key="test-key", query="")
        results = component.fetch_content()
        assert len(results) == 1
        assert "error" in results[0].data

    @patch("lfx.components.perplexity.perplexity_search.httpx.Client")
    def test_fetch_content_timeout_returns_error(self, mock_client_cls, component_class, default_kwargs):
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value.__enter__.return_value = mock_client

        component = component_class(**default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert results[0].data["error"] == "Request timed out (90.0s). Please try again or adjust parameters."

    @patch("lfx.components.perplexity.perplexity_search.logger")
    @patch("lfx.components.perplexity.perplexity_search.httpx.Client")
    def test_fetch_content_status_error_is_sanitized(
        self, mock_client_cls, mock_logger, component_class, default_kwargs
    ):
        request = httpx.Request("POST", "https://api.perplexity.ai/search")
        response = httpx.Response(429, text="upstream secret body", request=request)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "rate limited",
            request=request,
            response=response,
        )
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        component = component_class(**default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert results[0].data["error"] == "Perplexity API error: HTTP 429"
        assert "upstream secret body" not in str(results[0].data)
        mock_logger.error.assert_called_once_with("Perplexity API request failed with HTTP status 429.")

    @patch("lfx.components.perplexity.perplexity_search.httpx.Client")
    def test_fetch_content_request_error_returns_error(self, mock_client_cls, component_class, default_kwargs):
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.RequestError("network unavailable")
        mock_client_cls.return_value.__enter__.return_value = mock_client

        component = component_class(**default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert results[0].data["error"] == "Request error occurred: network unavailable"

    @patch("lfx.components.perplexity.perplexity_search.httpx.Client")
    def test_fetch_content_invalid_json_returns_error(self, mock_client_cls, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("invalid json")
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        component = component_class(**default_kwargs)
        results = component.fetch_content()

        assert len(results) == 1
        assert results[0].data["error"] == "Invalid response format: invalid json"

    @patch("lfx.components.perplexity.perplexity_search.httpx.Client")
    def test_fetch_content_dataframe(self, mock_client_cls, component_class, default_kwargs, fake_search_response):
        mock_response = MagicMock()
        mock_response.json.return_value = fake_search_response
        mock_response.raise_for_status.return_value = None
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        component = component_class(**default_kwargs)
        df = component.fetch_content_dataframe()
        assert isinstance(df, DataFrame)
        assert len(df) == 2

    @pytest.mark.asyncio
    async def test_latest_version(self, component_class, default_kwargs):
        """Override to skip network call."""
        component = component_class(**default_kwargs)
        assert component is not None
