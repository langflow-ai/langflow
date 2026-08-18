"""Unit tests for the Serply Search extension bundle (``lfx-serply``).

The component calls the Serply endpoint with ``httpx``; the tests patch
``httpx.get`` at the component module, so no network access is required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_serply import SerplySearchComponent

GET_PATCH_TARGET = "lfx_serply.components.serply.serply_search.httpx.get"

SAMPLE_PAYLOAD = {
    "results": [
        {
            "title": "Result one",
            "description": "First snippet.",
            "link": "https://example.com/one",
            "position": 1,
        },
        {
            "title": "Result two",
            "description": "Second snippet.",
            "link": "https://example.com/two",
            "position": 2,
        },
    ],
    "total": 2,
    "query": "hello",
}


def _mock_get(payload: dict) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return MagicMock(return_value=response)


@pytest.fixture
def component() -> SerplySearchComponent:
    c = SerplySearchComponent()
    c.input_value = "hello"
    c.serply_api_key = "test-key"  # pragma: allowlist secret
    c.max_results = 10
    return c


def test_component_metadata():
    """Class name must stay stable for saved flows."""
    assert SerplySearchComponent.__name__ == "SerplySearchComponent"


def test_missing_api_key_raises(component):
    """No key set -> clear ValueError instead of an anonymous request."""
    component.serply_api_key = ""
    with pytest.raises(ValueError, match="Serply API key is required"):
        component._search()


def test_search_sends_explicit_user_agent(component):
    """The request must carry an explicit User-Agent to clear Cloudflare (1010)."""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        component._search()
    headers = mock_get.call_args.kwargs["headers"]
    assert headers["User-Agent"]
    assert headers["User-Agent"] != ""
    assert headers["X-Api-Key"] == "test-key"  # pragma: allowlist secret


def test_search_builds_query_string_url(component):
    """The query is sent as a proper ``?``-delimited query string."""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        component._search()
    assert mock_get.call_args.args[0] == "https://api.serply.io/v1/search/?q=hello&num=10"


def test_max_results_is_clamped_high(component):
    """max_results above the range is clamped to the 100 upper bound."""
    component.max_results = 500
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        component._search()
    assert mock_get.call_args.args[0] == "https://api.serply.io/v1/search/?q=hello&num=100"


def test_max_results_is_clamped_low(component):
    """max_results below the range is clamped to the 1 lower bound."""
    component.max_results = 0
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        component._search()
    assert mock_get.call_args.args[0] == "https://api.serply.io/v1/search/?q=hello&num=1"


def test_fetch_content_maps_results(component):
    """Organic results map to Data(text=description, data={title,link,...})."""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert len(results) == 2
    assert results[0].text == "First snippet."
    assert results[0].data["title"] == "Result one"
    assert results[0].data["link"] == "https://example.com/one"
    assert results[0].data["position"] == 1


def test_fetch_content_handles_empty_results(component):
    """A payload with no results yields an empty list, not an error."""
    mock_get = _mock_get({"results": [], "total": 0})
    with patch(GET_PATCH_TARGET, mock_get):
        assert component.fetch_content() == []


def test_fetch_content_wraps_http_error(component):
    """A transport error is surfaced as a single error Data, not raised."""
    mock_get = MagicMock(side_effect=httpx.HTTPError("boom"))
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert len(results) == 1
    assert "boom" in results[0].data["error"]


def test_fetch_content_dataframe_shape(component):
    """The default output builds a DataFrame from the mapped results."""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        frame = component.fetch_content_dataframe()
    assert len(frame) == 2
