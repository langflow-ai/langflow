from unittest.mock import Mock, patch

import httpx
import pytest
from lfx.components.bocha.bocha_web_search import BOCHA_SEARCH_URL, BochaWebSearchComponent
from lfx.schema.data import Data
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient

TEST_BOCHA_API_KEY = "bocha-test-api-key"  # pragma: allowlist secret


class TestBochaWebSearchComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return BochaWebSearchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": TEST_BOCHA_API_KEY,
            "query": "langflow",
            "freshness": "noLimit",
            "summary": True,
            "count": 3,
            "include": "docs.langflow.org|github.com",
            "exclude": "example.com,foo.dev",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_component_initialization(self, component_class):
        component = component_class()

        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]

        assert node_data["display_name"] == "Bocha Web Search"
        assert node_data["icon"] == "Bocha"

        template = node_data["template"]
        assert "api_key" in template
        assert "query" in template
        assert "freshness" in template
        assert "summary" in template
        assert "count" in template
        assert "include" in template
        assert "exclude" in template
        assert template["query"]["type"] == "query"
        assert template["query"]["tool_mode"] is True
        assert template["freshness"]["advanced"] is False
        assert template["freshness"]["tool_mode"] is True
        assert template["summary"]["advanced"] is False
        assert template["count"]["advanced"] is False
        assert template["count"]["tool_mode"] is True
        assert template["summary"]["display_name"] == "Include Summary"
        assert template["include"]["advanced"] is True
        assert template["exclude"]["advanced"] is True

    @patch("lfx.components.bocha.bocha_web_search.httpx.Client")
    def test_fetch_content_success(self, mock_client_class, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "code": 200,
            "log_id": "test-log-id",
            "msg": None,
            "data": {
                "_type": "SearchResponse",
                "queryContext": {"originalQuery": "langflow"},
                "webPages": {
                    "totalEstimatedMatches": 2,
                    "value": [
                        {
                            "id": "1",
                            "name": "Langflow Docs",
                            "url": "https://docs.langflow.org/",
                            "displayUrl": "docs.langflow.org",
                            "snippet": "Langflow documentation",
                            "summary": "Official Langflow documentation",
                            "siteName": "Langflow",
                            "siteIcon": "https://docs.langflow.org/icon.png",
                            "datePublished": "2025-05-01T08:00:00+08:00",
                            "cachedPageUrl": "https://cache.langflow.org/docs",
                            "language": "en",
                            "isFamilyFriendly": True,
                            "isNavigational": False,
                        },
                        {
                            "id": "2",
                            "name": "Langflow GitHub",
                            "url": "https://github.com/langflow-ai/langflow",
                            "displayUrl": "github.com/langflow-ai/langflow",
                            "snippet": "Langflow source code",
                            "summary": "",
                            "siteName": "GitHub",
                            "siteIcon": "https://github.com/favicon.ico",
                            "datePublished": "2025-05-02T08:00:00+08:00",
                            "cachedPageUrl": "https://cache.langflow.org/github",
                            "language": "en",
                            "isFamilyFriendly": True,
                            "isNavigational": True,
                        },
                    ],
                },
            },
        }

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = component.fetch_content()

        assert isinstance(result, Data)
        assert result.data["data"]["webPages"]["totalEstimatedMatches"] == 2
        assert result.data["data"]["webPages"]["value"][0]["id"] == "1"
        assert result.data["data"]["webPages"]["value"][0]["name"] == "Langflow Docs"
        assert result.data["data"]["webPages"]["value"][0]["displayUrl"] == "docs.langflow.org"
        assert result.data["data"]["webPages"]["value"][0]["summary"] == "Official Langflow documentation"
        assert "text" not in result.data
        mock_client.post.assert_called_once_with(
            BOCHA_SEARCH_URL,
            json={
                "query": "langflow",
                "summary": True,
                "count": 3,
                "freshness": "noLimit",
                "include": "docs.langflow.org|github.com",
                "exclude": "example.com|foo.dev",
            },
            headers={
                "Authorization": f"Bearer {TEST_BOCHA_API_KEY}",
                "Content-Type": "application/json",
            },
        )

    @patch("lfx.components.bocha.bocha_web_search.httpx.Client")
    def test_fetch_content_http_error(self, mock_client_class, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        request = httpx.Request("POST", BOCHA_SEARCH_URL)
        response = httpx.Response(401, request=request, text="Invalid API KEY")
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized",
            request=request,
            response=response,
        )
        mock_response.text = "Invalid API KEY"
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = component.fetch_content()

        assert isinstance(result, Data)
        assert "HTTP error occurred: 401" in result.data["error"]

    def test_fetch_content_validation_error(self, component_class):
        component = component_class(api_key=TEST_BOCHA_API_KEY, query="", count=51)

        result = component.fetch_content()

        assert isinstance(result, Data)
        assert "Empty search query." in result.data["error"]

    def test_fetch_content_text(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component._request_search_results = Mock(
            return_value={
                "data": {
                    "webPages": {
                        "value": [
                            {
                                "name": "first result",
                                "url": "https://example.com/1",
                                "summary": "first summary",
                                "datePublished": "2025-05-01T08:00:00+08:00",
                            },
                            {
                                "name": "second result",
                                "url": "https://example.com/2",
                                "summary": "second summary",
                                "datePublished": "2025-05-02T08:00:00+08:00",
                            },
                        ]
                    }
                }
            }
        )

        result = component.fetch_content_text()

        assert isinstance(result, Message)
        assert "[[引用:1]]" in result.text
        assert "first result" in result.text
        assert "second result" in result.text

    @patch("lfx.components.bocha.bocha_web_search.httpx.Client")
    def test_fetch_content_empty_results(self, mock_client_class, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"data": {"webPages": {"value": []}}}
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = component.fetch_content()

        assert isinstance(result, Data)
        assert result.data == {"data": {"webPages": {"value": []}}}
        assert "text" not in result.data

    @pytest.mark.asyncio
    async def test_latest_version(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        assert component is not None
