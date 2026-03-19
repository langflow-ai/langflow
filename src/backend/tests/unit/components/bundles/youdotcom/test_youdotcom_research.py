from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx.components.youdotcom.youdotcom_research import YouDotComResearchComponent

from tests.base import ComponentTestBaseWithoutClient

MOCK_RESEARCH_RESPONSE = {
    "output": {
        "content": "# Quantum Computing Advances\n\nRecent developments include...",
        "content_type": "text",
        "sources": [
            {
                "url": "https://example.com/quantum",
                "title": "Quantum Computing Research",
                "snippets": ["Recent breakthroughs in quantum error correction..."],
            },
            {
                "url": "https://example.org/physics",
                "title": "Physics Today",
            },
        ],
    },
}


def _mock_httpx_client(mock_client_class, mock_response):
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_class.return_value = mock_client
    return mock_client


class TestYouDotComResearchComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return YouDotComResearchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-ydc-key",
            "query": "What are the latest advances in quantum computing?",
            "research_effort": "standard",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_basic_setup(self, component_class, default_kwargs):
        component = component_class()
        component.set_attributes(default_kwargs)

        assert component.display_name == "You.com Research"
        assert component.icon == "YouDotCom"
        assert component.api_key == "test-ydc-key"
        assert component.research_effort == "standard"

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
    def test_research_answer_success(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_RESEARCH_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_client = _mock_httpx_client(mock_client_class, mock_response)

        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.research_answer()

        assert "Quantum Computing Advances" in result.text

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["headers"]["User-Agent"] == "langflow-youdotcom/1.0"
        assert call_kwargs[1]["headers"]["X-API-Key"] == "test-ydc-key"

        payload = call_kwargs[1]["json"]
        assert payload["input"] == "What are the latest advances in quantum computing?"
        assert payload["research_effort"] == "standard"
        assert "query" not in payload

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
    def test_research_sources_success(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_RESEARCH_RESPONSE
        mock_response.raise_for_status = MagicMock()
        _mock_httpx_client(mock_client_class, mock_response)

        component = component_class()
        component.set_attributes(default_kwargs)
        df = component.research_sources()

        assert df is not None
        assert len(df) == 2
        assert df.iloc[0]["url"] == "https://example.com/quantum"
        assert df.iloc[0]["title"] == "Quantum Computing Research"
        assert df.iloc[1]["url"] == "https://example.org/physics"

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
    def test_api_uses_input_not_query(self, mock_client_class, component_class, default_kwargs):
        """Verify the API request body uses 'input' param, not 'query'."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {"content": "Answer", "content_type": "text", "sources": []},
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = _mock_httpx_client(mock_client_class, mock_response)

        component = component_class()
        component.set_attributes(default_kwargs)
        component.research_answer()

        payload = mock_client.post.call_args[1]["json"]
        assert "input" in payload
        assert "query" not in payload

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
    def test_research_answer_timeout(self, mock_client_class, component_class, default_kwargs):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("timed out")
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.research_answer()

        assert "timed out" in result.text.lower()

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
    def test_research_answer_http_error(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_response
        )
        _mock_httpx_client(mock_client_class, mock_response)

        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.research_answer()

        assert "500" in result.text

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
    def test_research_sources_timeout(self, mock_client_class, component_class, default_kwargs):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("timed out")
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        df = component.research_sources()

        assert df is not None

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
    def test_posts_to_correct_url(self, mock_client_class, component_class, default_kwargs):
        """Verify Research API uses api.you.com, not ydc-index.io."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {"content": "Answer", "content_type": "text", "sources": []},
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = _mock_httpx_client(mock_client_class, mock_response)

        component = component_class()
        component.set_attributes(default_kwargs)
        component.research_answer()

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.you.com/v1/research"
