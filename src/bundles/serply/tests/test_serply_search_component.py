"""Unit tests for the Serply Search extension bundle (``lfx-serply``).

The component calls the Serply endpoint with ``httpx``; the tests patch
``httpx.get`` at the component module to return real ``httpx.Response``
objects, so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_serply import SerplySearchComponent

GET_PATCH_TARGET = "lfx_serply.components.serply.serply_search.httpx.get"
SEARCH_URL = "https://api.serply.io/v1/search/"

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


def _response(status_code: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("GET", SEARCH_URL), **kwargs)


def _mock_get(payload: object) -> MagicMock:
    return MagicMock(return_value=_response(json=payload))


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


def test_fetch_content_reports_missing_api_key_without_request(component):
    """The public output turns a missing key into an error row and never calls Serply."""
    component.serply_api_key = ""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    mock_get.assert_not_called()
    assert len(results) == 1
    assert "Serply API key is required" in results[0].data["error"]


def test_search_sends_explicit_user_agent(component):
    """The request must carry an explicit User-Agent to clear Cloudflare (1010)."""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        component._search()
    headers = mock_get.call_args.kwargs["headers"]
    assert headers["User-Agent"] == "langflow-serply-bundle"
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


def test_max_results_range_spec_matches_clamp():
    """The UI range matches the bounds the request clamps to."""
    max_results = next(i for i in SerplySearchComponent.inputs if i.name == "max_results")
    assert max_results.range_spec is not None
    assert (max_results.range_spec.min, max_results.range_spec.max) == (1, 100)
    assert max_results.range_spec.step_type == "int"


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


def test_fetch_content_skips_malformed_results(component):
    """Result entries that are not JSON objects are skipped instead of crashing."""
    mock_get = _mock_get({"results": ["not-an-object", SAMPLE_PAYLOAD["results"][0]]})
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert [r.data["title"] for r in results] == ["Result one"]


def test_fetch_content_rejects_non_object_payload(component):
    """A JSON body that is not an object becomes an error row, not an AttributeError."""
    mock_get = _mock_get(["unexpected"])
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert len(results) == 1
    assert "unexpected response" in results[0].data["error"]


def test_fetch_content_wraps_http_error(component):
    """A transport error is surfaced as a single error Data, not raised."""
    mock_get = MagicMock(side_effect=httpx.HTTPError("boom"))
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert len(results) == 1
    assert "boom" in results[0].data["error"]


def test_fetch_content_surfaces_api_error_detail(component):
    """A 401 keeps Serply's own reason instead of the generic httpx message."""
    mock_get = MagicMock(return_value=_response(401, json={"detail": "Invalid API key"}))
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert len(results) == 1
    assert results[0].data["error"] == "Serply API error 401: Invalid API key"


def test_fetch_content_http_error_without_json_body(component):
    """A non-JSON error body falls back to the HTTP reason phrase."""
    mock_get = MagicMock(return_value=_response(502, text="upstream down"))
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert results[0].data["error"] == "Serply API error 502: Bad Gateway"


def test_serply_search_dataframe_shape(component):
    """The default output builds a DataFrame from the mapped results."""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        frame = component.serply_search()
    assert len(frame) == 2


def test_tool_mode_exposes_a_serply_specific_tool():
    """The agent-facing tool name must not collide with other search components."""
    # Tools read inputs the way a graph sets them (constructor kwargs), not
    # attributes assigned after construction, so build the component directly.
    component = SerplySearchComponent(serply_api_key="test-key", max_results=10)  # pragma: allowlist secret
    tools = asyncio.run(component.to_toolkit())
    assert [tool.name for tool in tools] == ["serply_search"]

    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        output = asyncio.run(tools[0].ainvoke({"input_value": "langflow"}))
    assert mock_get.call_args.args[0] == "https://api.serply.io/v1/search/?q=langflow&num=10"
    assert "Result one" in str(output)
