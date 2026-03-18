from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx.components.youdotcom.youdotcom_research import YouDotComResearchComponent

from tests.base import ComponentTestBaseWithoutClient


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
    def test_fetch_content_success(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = {
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
        assert "Quantum Computing Advances" in results[0].text
        assert results[0].data["content_type"] == "text"
        assert len(results[0].data["sources"]) == 2
        assert results[0].data["sources"][0]["url"] == "https://example.com/quantum"

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["headers"]["User-Agent"] == "langflow-youdotcom/1.0"
        assert call_kwargs[1]["headers"]["X-API-Key"] == "test-ydc-key"

        payload = call_kwargs[1]["json"]
        assert payload["input"] == "What are the latest advances in quantum computing?"
        assert payload["research_effort"] == "standard"
        assert "query" not in payload

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
    def test_fetch_content_uses_input_not_query(self, mock_client_class, component_class, default_kwargs):
        """Verify the API request body uses 'input' param, not 'query'."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {"content": "Answer", "content_type": "text", "sources": []},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        component.fetch_content()

        payload = mock_client.post.call_args[1]["json"]
        assert "input" in payload
        assert "query" not in payload

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
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

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
    def test_fetch_content_http_error(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_response
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
        assert "500" in results[0].text
        assert "error" in results[0].data

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
    def test_fetch_content_posts_to_correct_url(self, mock_client_class, component_class, default_kwargs):
        """Verify Research API uses api.you.com, not ydc-index.io."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {"content": "Answer", "content_type": "text", "sources": []},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        component = component_class()
        component.set_attributes(default_kwargs)
        component.fetch_content()

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.you.com/v1/research"

    @patch("lfx.components.youdotcom.youdotcom_research.httpx.Client")
    def test_fetch_content_dataframe(self, mock_client_class, component_class, default_kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {"content": "Answer", "content_type": "text", "sources": []},
        }
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
