"""Unit tests for the Serping API Search extension bundle (``lfx-serpingapi``).

The component calls the Serping API endpoint with ``httpx``; the tests patch
``httpx.post`` at the component module to return real ``httpx.Response``
objects, so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_serpingapi import SerpingApiSearchComponent

POST_PATCH_TARGET = "lfx_serpingapi.components.serpingapi.serpingapi_search.httpx.post"
SEARCH_URL = "https://api.serpingapi.com/v1/search"

SAMPLE_PAYLOAD = {
    "searchParameters": {"q": "hello", "type": "search"},
    "organic": [
        {
            "title": "Result one",
            "snippet": "First snippet.",
            "link": "https://example.com/one",
            "position": 1,
        },
        {
            "title": "Result two",
            "snippet": "Second snippet.",
            "link": "https://example.com/two",
            "position": 2,
        },
    ],
    "relatedSearches": [{"query": "hello world"}],
}


def _response(status_code: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("POST", SEARCH_URL), **kwargs)


def _mock_post(payload: object) -> MagicMock:
    return MagicMock(return_value=_response(json=payload))


@pytest.fixture
def component() -> SerpingApiSearchComponent:
    c = SerpingApiSearchComponent()
    c.input_value = "hello"
    c.serpingapi_api_key = "test-key"  # pragma: allowlist secret
    c.max_results = 10
    c.page = 1
    c.gl = ""
    c.hl = ""
    c.location = ""
    return c


def test_component_metadata():
    """Class name must stay stable for saved flows."""
    assert SerpingApiSearchComponent.__name__ == "SerpingApiSearchComponent"


def test_missing_api_key_raises(component):
    """No key set -> clear ValueError instead of an anonymous request."""
    component.serpingapi_api_key = ""
    with pytest.raises(ValueError, match="Serping API key is required"):
        component._search()


def test_fetch_content_reports_missing_api_key_without_request(component):
    """The public output turns a missing key into an error row and never calls the API."""
    component.serpingapi_api_key = ""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    mock_post.assert_not_called()
    assert len(results) == 1
    assert "Serping API key is required" in results[0].data["error"]


def test_search_sends_api_key_header_and_json_body(component):
    """The request is a POST to the search endpoint with the key in X-API-Key."""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.args[0] == SEARCH_URL
    headers = mock_post.call_args.kwargs["headers"]
    assert headers["X-API-Key"] == "test-key"  # pragma: allowlist secret
    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"] == "langflow-serpingapi-bundle"
    assert mock_post.call_args.kwargs["json"] == {"q": "hello", "num": 10}


def test_search_includes_optional_localization_and_page(component):
    """gl, hl, location and page are sent only when set; page 1 is the default and omitted."""
    component.gl = "de"
    component.hl = "en"
    component.location = " Berlin, Germany "
    component.page = 3
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.kwargs["json"] == {
        "q": "hello",
        "num": 10,
        "gl": "de",
        "hl": "en",
        "location": "Berlin, Germany",
        "page": 3,
    }


def test_max_results_is_clamped_high(component):
    """max_results above the range is clamped to the 100 upper bound."""
    component.max_results = 500
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.kwargs["json"]["num"] == 100


def test_max_results_is_clamped_low(component):
    """max_results below the range is clamped to the 1 lower bound."""
    component.max_results = 0
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.kwargs["json"]["num"] == 1


def test_max_results_range_spec_matches_clamp():
    """The UI range matches the bounds the request clamps to."""
    max_results = next(i for i in SerpingApiSearchComponent.inputs if i.name == "max_results")
    assert max_results.range_spec is not None
    assert (max_results.range_spec.min, max_results.range_spec.max) == (1, 100)
    assert max_results.range_spec.step_type == "int"


def test_fetch_content_maps_results(component):
    """Organic results map to Data(text=snippet, data={title,link,snippet,position})."""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 2
    assert results[0].text == "First snippet."
    assert results[0].data["title"] == "Result one"
    assert results[0].data["link"] == "https://example.com/one"
    assert results[0].data["snippet"] == "First snippet."
    assert results[0].data["position"] == 1


def test_fetch_content_handles_empty_results(component):
    """A payload with no organic results yields an empty list, not an error."""
    mock_post = _mock_post({"searchParameters": {"q": "hello"}, "organic": []})
    with patch(POST_PATCH_TARGET, mock_post):
        assert component.fetch_content() == []


def test_fetch_content_handles_missing_organic_section(component):
    """The API omits sections Google did not return; a missing organic key is an empty list."""
    mock_post = _mock_post({"searchParameters": {"q": "hello"}, "answerBox": {"answer": "42"}})
    with patch(POST_PATCH_TARGET, mock_post):
        assert component.fetch_content() == []


def test_fetch_content_skips_malformed_results(component):
    """Result entries that are not JSON objects are skipped instead of crashing."""
    mock_post = _mock_post({"organic": ["not-an-object", SAMPLE_PAYLOAD["organic"][0]]})
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert [r.data["title"] for r in results] == ["Result one"]


def test_fetch_content_rejects_non_object_payload(component):
    """A JSON body that is not an object becomes an error row, not an AttributeError."""
    mock_post = _mock_post(["unexpected"])
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 1
    assert "unexpected response" in results[0].data["error"]


def test_fetch_content_wraps_http_error(component):
    """A transport error is surfaced as a single error Data, not raised."""
    mock_post = MagicMock(side_effect=httpx.HTTPError("boom"))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 1
    assert "boom" in results[0].data["error"]


def test_fetch_content_surfaces_api_error_message(component):
    """A 401 keeps the API's own error message instead of the generic httpx message."""
    body = {"error": {"code": "invalid_api_key", "message": "The API key is wrong or revoked."}}
    mock_post = MagicMock(return_value=_response(401, json=body))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 1
    assert results[0].data["error"] == "Serping API error 401: The API key is wrong or revoked."


def test_fetch_content_surfaces_quota_error(component):
    """A 429 quota error is reported with the API's message."""
    body = {"error": {"code": "quota_exceeded", "message": "Monthly quota of 1,000 searches reached."}}
    mock_post = MagicMock(return_value=_response(429, json=body))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert results[0].data["error"] == "Serping API error 429: Monthly quota of 1,000 searches reached."


def test_fetch_content_http_error_without_json_body(component):
    """A non-JSON error body falls back to the HTTP reason phrase."""
    mock_post = MagicMock(return_value=_response(502, text="upstream down"))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert results[0].data["error"] == "Serping API error 502: Bad Gateway"


def test_serpingapi_search_dataframe_shape(component):
    """The default output builds a DataFrame from the mapped results."""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        frame = component.serpingapi_search()
    assert len(frame) == 2


def test_tool_mode_exposes_a_serpingapi_specific_tool():
    """The agent-facing tool name must not collide with other search components."""
    # Tools read inputs the way a graph sets them (constructor kwargs), not
    # attributes assigned after construction, so build the component directly.
    component = SerpingApiSearchComponent(serpingapi_api_key="test-key", max_results=10)  # pragma: allowlist secret
    tools = asyncio.run(component.to_toolkit())
    assert [tool.name for tool in tools] == ["serpingapi_search"]

    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        output = asyncio.run(tools[0].ainvoke({"input_value": "langflow"}))
    assert mock_post.call_args.kwargs["json"] == {"q": "langflow", "num": 10}
    assert "Result one" in str(output)
