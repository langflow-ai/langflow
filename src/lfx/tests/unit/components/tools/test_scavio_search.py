"""Unit test for the Scavio Langflow component.

Destination in the Langflow repo:
  src/lfx/tests/unit/components/tools/test_scavio_search.py

Patches httpx so it runs offline in CI (no extra test dependency). Mirrors the
real Scavio v2 wire shape (organic_results with link/snippet).
"""

from unittest.mock import MagicMock, patch

from lfx.components.scavio.scavio_search import ScavioSearchComponent
from lfx.schema.dataframe import DataFrame

MOCK_RESPONSE = {
    "search_parameters": {"q": "openai"},
    "credits_used": 1,
    "organic_results": [
        {
            "title": f"Result {i}",
            "link": f"https://example.com/{i}",
            "snippet": f"Description {i}",
            "position": i,
        }
        for i in range(1, 6)
    ],
}


def _mock_post(status_code=200, json_data=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data if json_data is not None else MOCK_RESPONSE
    response.text = text
    if status_code >= 400:
        import httpx

        response.raise_for_status.side_effect = httpx.HTTPStatusError("error", request=MagicMock(), response=response)
    else:
        response.raise_for_status.return_value = None
    client = MagicMock()
    client.__enter__.return_value.post.return_value = response
    return client


def test_fetch_content_returns_data():
    with patch("httpx.Client", return_value=_mock_post()):
        component = ScavioSearchComponent(api_key="sk_live_test", query="openai")
        results = component.fetch_content()

    assert len(results) == 5
    assert results[0].data["title"] == "Result 1"
    assert results[0].data["url"] == "https://example.com/1"
    assert results[0].text == "Description 1"


def test_fetch_content_respects_max_results():
    with patch("httpx.Client", return_value=_mock_post()):
        component = ScavioSearchComponent(api_key="sk_live_test", query="openai", max_results=2)
        assert len(component.fetch_content()) == 2


def test_fetch_content_dataframe():
    with patch("httpx.Client", return_value=_mock_post()):
        component = ScavioSearchComponent(api_key="sk_live_test", query="openai")
        assert isinstance(component.fetch_content_dataframe(), DataFrame)


def test_http_error_is_handled():
    with patch("httpx.Client", return_value=_mock_post(status_code=401, text="unauthorized")):
        component = ScavioSearchComponent(api_key="bad", query="openai")
        results = component.fetch_content()
    assert len(results) == 1
    assert "error" in results[0].data
