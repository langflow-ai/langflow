from unittest.mock import Mock, patch

import httpx
import pytest
from lfx.components.bocha.bocha_web_search import (
    BOCHA_COUNT_VALIDATION_MESSAGE,
    BOCHA_EMPTY_RESULTS_MESSAGE,
    BOCHA_SEARCH_URL,
    BochaWebSearchComponent,
)
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

    @pytest.fixture
    def sample_search_response(self):
        return {
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
        assert template["count"]["tool_mode"] is False
        assert template["summary"]["display_name"] == "Include Summary"
        assert template["include"]["advanced"] is True
        assert template["exclude"]["advanced"] is True

    def test_split_domains_normalizes_separators(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        assert (
            component._split_domains(" docs.langflow.org | github.com, foo.dev ")
            == "docs.langflow.org|github.com|foo.dev"
        )
        assert component._split_domains("") is None
        assert component._split_domains(None) is None

    def test_parse_count_returns_integer(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        assert component._parse_count() == 3

    def test_parse_count_raises_stable_error_for_invalid_count(self, component_class, default_kwargs):
        component = component_class(**(default_kwargs | {"count": "not-a-number"}))

        with pytest.raises(ValueError, match=r"Max Results must be an integer between 1 and 50\."):
            component._parse_count()

    def test_build_payload_normalizes_domains(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        assert component._build_payload() == {
            "query": "langflow",
            "summary": True,
            "count": 3,
            "freshness": "noLimit",
            "include": "docs.langflow.org|github.com",
            "exclude": "example.com|foo.dev",
        }

    @pytest.mark.parametrize(
        ("kwargs", "expected_error"),
        [
            ({"api_key": "", "query": "langflow", "count": 3}, "Missing Bocha API Key."),
            ({"api_key": TEST_BOCHA_API_KEY, "query": "", "count": 3}, "Empty search query."),
            (
                {"api_key": TEST_BOCHA_API_KEY, "query": "langflow", "count": 51},
                "Max Results must be between 1 and 50.",
            ),
            (
                {"api_key": TEST_BOCHA_API_KEY, "query": "langflow", "count": "bad-count"},
                BOCHA_COUNT_VALIDATION_MESSAGE,
            ),
            (
                {
                    "api_key": TEST_BOCHA_API_KEY,
                    "query": "langflow",
                    "count": 3,
                    "freshness": "today",
                },
                "Invalid freshness value: today",
            ),
        ],
    )
    def test_validate_search_inputs_returns_expected_errors(self, component_class, kwargs, expected_error):
        component = component_class(**kwargs)

        assert component._validate_search_inputs() == expected_error

    @patch("lfx.components.bocha.bocha_web_search.httpx.Client")
    def test_request_search_results_uses_cached_response(
        self, mock_client_class, component_class, default_kwargs, sample_search_response
    ):
        component = component_class(**default_kwargs)

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = sample_search_response
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        first_result = component._request_search_results()
        second_result = component._request_search_results()

        assert first_result == sample_search_response
        assert second_result == sample_search_response
        mock_client.post.assert_called_once()

    @patch("lfx.components.bocha.bocha_web_search.httpx.Client")
    def test_fetch_content_success(self, mock_client_class, component_class, default_kwargs, sample_search_response):
        component = component_class(**default_kwargs)

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = sample_search_response

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

    @patch("lfx.components.bocha.bocha_web_search.httpx.Client")
    def test_fetch_content_text(self, mock_client_class, component_class, default_kwargs, sample_search_response):
        component = component_class(**default_kwargs)

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = sample_search_response
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = component.fetch_content_text()

        assert isinstance(result, Message)
        assert "[[Reference:1]]" in result.text
        assert "Webpage Title: Langflow Docs" in result.text
        assert "Webpage Content: Official Langflow documentation" in result.text
        assert "Webpage Title: Langflow GitHub" in result.text
        assert "Webpage Content: Langflow source code" in result.text

    @pytest.mark.parametrize(
        "search_results",
        [
            None,
            "invalid-payload",
            {"data": None},
            {"data": []},
            {"data": {"webPages": None}},
            {"data": {"webPages": {"value": None}}},
            {"data": {"webPages": {"value": ["invalid-context"]}}},
        ],
    )
    def test_build_text_output_handles_non_dict_payloads(self, component_class, default_kwargs, search_results):
        component = component_class(**default_kwargs)

        assert component._build_text_output(search_results) == BOCHA_EMPTY_RESULTS_MESSAGE

    def test_build_text_output_limits_results_to_ten(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        contexts = [
            {
                "name": f"result-{index}",
                "url": f"https://example.com/{index}",
                "summary": f"summary-{index}",
                "datePublished": f"2025-05-{index + 1:02d}T08:00:00+08:00",
                "siteName": "Example",
            }
            for index in range(12)
        ]

        result = component._build_text_output({"data": {"webPages": {"value": contexts}}})

        assert "[[Reference:10]]" in result
        assert "[[Reference:11]]" not in result

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

    @patch("lfx.components.bocha.bocha_web_search.httpx.Client")
    def test_fetch_content_timeout_error(self, mock_client_class, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        mock_client = Mock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = component.fetch_content()

        assert isinstance(result, Data)
        assert "Request timed out (90s)." in result.data["error"]

    @patch("lfx.components.bocha.bocha_web_search.httpx.Client")
    def test_fetch_content_request_error(self, mock_client_class, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        mock_client = Mock()
        mock_client.post.side_effect = httpx.RequestError("network down")
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = component.fetch_content()

        assert isinstance(result, Data)
        assert "Request error occurred: network down" in result.data["error"]

    @patch("lfx.components.bocha.bocha_web_search.httpx.Client")
    def test_fetch_content_text_request_error(self, mock_client_class, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        mock_client = Mock()
        mock_client.post.side_effect = httpx.RequestError("network down")
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = component.fetch_content_text()

        assert isinstance(result, Message)
        assert result.text == "Request error occurred: network down"

    def test_run_model_delegates_to_fetch_content(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        expected = Data(data={"ok": True})

        with patch.object(component, "fetch_content", return_value=expected) as fetch_content:
            result = component.run_model()

        assert result == expected
        fetch_content.assert_called_once_with()
