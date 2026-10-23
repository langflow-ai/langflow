"""Unit tests for the CrawlerData Search extension bundle (``lfx-crawlerdata``).

The component calls the CrawlerData API with ``httpx``; the tests patch
``httpx.post`` at the component module to return real ``httpx.Response``
objects, so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_crawlerdata import CrawlerDataSearchComponent

POST_PATCH_TARGET = "lfx_crawlerdata.components.crawlerdata.crawlerdata_search.httpx.post"
JOBS_URL = "https://api.crawlerdata.com/v1/jobs"

SAMPLE_PAYLOAD = {
    "job": {"status": "completed", "credits": 1},
    "result": {
        "search_parameters": {"query": "hello"},
        "ai_overview": {
            "text": "Hello is a greeting.",
            "sources": [
                {"title": "Wikipedia", "link": "https://en.wikipedia.org/wiki/Hello"},
                {"title": "No link", "link": ""},
            ],
        },
        "organic_results": [
            {
                "position": 1,
                "title": "Result one",
                "link": "https://example.com/one",
                "displayed_link": "example.com",
                "snippet": "First snippet.",
            },
            {
                "position": 2,
                "title": "Result two",
                "link": "https://example.com/two",
                "displayed_link": "example.com",
                "snippet": "Second snippet.",
            },
        ],
        "related_searches": [{"query": "hello world"}],
    },
}


def _response(status_code: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("POST", JOBS_URL), **kwargs)


def _mock_post(payload: object) -> MagicMock:
    return MagicMock(return_value=_response(json=payload))


@pytest.fixture
def component() -> CrawlerDataSearchComponent:
    c = CrawlerDataSearchComponent()
    c.input_value = "hello"
    c.crawlerdata_api_key = "test-key"  # pragma: allowlist secret
    c.country = "us"
    c.language = ""
    c.device = "desktop"
    c.location = ""
    c.max_results = 10
    c.page = 1
    c.include_ai_overview = True
    return c


def test_component_metadata():
    """Class name must stay stable for saved flows."""
    assert CrawlerDataSearchComponent.__name__ == "CrawlerDataSearchComponent"


def test_missing_api_key_raises(component):
    """No key set -> clear ValueError instead of an anonymous request."""
    component.crawlerdata_api_key = ""
    with pytest.raises(ValueError, match="CrawlerData API key is required"):
        component._search()


def test_fetch_content_reports_missing_api_key_without_request(component):
    """The public output turns a missing key into an error row and never calls the API."""
    component.crawlerdata_api_key = ""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    mock_post.assert_not_called()
    assert len(results) == 1
    assert "CrawlerData API key is required" in results[0].data["error"]


def test_search_sends_bearer_key_and_live_google_search_job(component):
    """The request is a POST to the jobs endpoint with the key as a Bearer token."""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.args[0] == JOBS_URL
    headers = mock_post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"  # pragma: allowlist secret
    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"] == "langflow-crawlerdata-bundle"
    assert mock_post.call_args.kwargs["json"] == {
        "endpoint": "google-search",
        "params": {"query": "hello", "country": "us", "device": "desktop"},
        "queue": "live",
    }


def test_search_includes_optional_localization_and_page(component):
    """language, location and page are sent only when set; page 1 is the default and omitted."""
    component.country = "de"
    component.language = "en"
    component.device = "mobile"
    component.location = " Berlin,Berlin,Germany "
    component.page = 3
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.kwargs["json"]["params"] == {
        "query": "hello",
        "country": "de",
        "language": "en",
        "device": "mobile",
        "location": "Berlin,Berlin,Germany",
        "page": 3,
    }


def test_country_defaults_to_us_when_empty(component):
    """An empty country falls back to 'us' so the request is always valid."""
    component.country = ""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.kwargs["json"]["params"]["country"] == "us"


def test_max_results_range_spec_matches_clamp():
    """The UI range matches the bounds the results are clamped to."""
    max_results = next(i for i in CrawlerDataSearchComponent.inputs if i.name == "max_results")
    assert max_results.range_spec is not None
    assert (max_results.range_spec.min, max_results.range_spec.max) == (1, 100)
    assert max_results.range_spec.step_type == "int"


def test_max_results_limits_organic_rows(component):
    """max_results caps the organic rows (the AI Overview row is extra)."""
    component.max_results = 1
    component.include_ai_overview = False
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert [r.data["title"] for r in results] == ["Result one"]


def test_max_results_is_clamped_low(component):
    """max_results below the range is clamped to one organic row."""
    component.max_results = 0
    component.include_ai_overview = False
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 1


def test_fetch_content_maps_organic_results(component):
    """Organic results map to Data(text=snippet, data={title,link,snippet,position})."""
    component.include_ai_overview = False
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 2
    assert results[0].text == "First snippet."
    assert results[0].data["title"] == "Result one"
    assert results[0].data["link"] == "https://example.com/one"
    assert results[0].data["snippet"] == "First snippet."
    assert results[0].data["position"] == 1


def test_fetch_content_adds_ai_overview_row_first(component):
    """The AI Overview is the first row (position 0) and lists the pages it cites that have a link."""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 3
    overview = results[0]
    assert overview.data["title"] == "Google AI Overview"
    assert overview.data["position"] == 0
    assert overview.data["snippet"].startswith("Hello is a greeting.")
    assert "- Wikipedia: https://en.wikipedia.org/wiki/Hello" in overview.data["snippet"]
    assert "No link" not in overview.data["snippet"]
    assert [r.data["title"] for r in results[1:]] == ["Result one", "Result two"]


def test_ai_overview_can_be_turned_off(component):
    """include_ai_overview=False returns only the organic rows."""
    component.include_ai_overview = False
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert [r.data["title"] for r in results] == ["Result one", "Result two"]


def test_no_ai_overview_row_when_google_shows_none(component):
    """No AI Overview in the result -> no extra row."""
    payload = {"result": {"organic_results": SAMPLE_PAYLOAD["result"]["organic_results"], "ai_overview": None}}
    mock_post = _mock_post(payload)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert [r.data["title"] for r in results] == ["Result one", "Result two"]


def test_fetch_content_handles_empty_results(component):
    """A result with no organic results yields an empty list, not an error."""
    mock_post = _mock_post({"result": {"organic_results": []}})
    with patch(POST_PATCH_TARGET, mock_post):
        assert component.fetch_content() == []


def test_fetch_content_skips_malformed_results(component):
    """Result entries that are not JSON objects are skipped instead of crashing."""
    component.include_ai_overview = False
    first = SAMPLE_PAYLOAD["result"]["organic_results"][0]
    mock_post = _mock_post({"result": {"organic_results": ["not-an-object", first]}})
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert [r.data["title"] for r in results] == ["Result one"]


def test_fetch_content_rejects_unexpected_payload(component):
    """A JSON body without a result object becomes an error row, not an AttributeError."""
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
    assert results[0].data["error"] == "CrawlerData API request failed: HTTPError: boom"


def test_fetch_content_names_transport_errors_with_empty_message(component):
    """A timeout whose message is empty still yields a readable error naming the exception type."""
    mock_post = MagicMock(side_effect=httpx.ReadTimeout(""))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert results[0].data["error"] == "CrawlerData API request failed: ReadTimeout"


def test_fetch_content_surfaces_api_error_message(component):
    """A 401 keeps the API's own error message instead of the generic httpx message."""
    body = {"error": {"code": "UNAUTHORIZED", "message": "Invalid API key"}}
    mock_post = MagicMock(return_value=_response(401, json=body))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 1
    assert results[0].data["error"] == "CrawlerData API error 401: Invalid API key"


def test_fetch_content_surfaces_out_of_credits_error(component):
    """A 402 (out of credits) is reported with the API's message."""
    body = {"error": {"code": "INSUFFICIENT_CREDITS", "message": "Not enough credits"}}
    mock_post = MagicMock(return_value=_response(402, json=body))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert results[0].data["error"] == "CrawlerData API error 402: Not enough credits"


def test_fetch_content_http_error_without_json_body(component):
    """A non-JSON error body falls back to the HTTP reason phrase."""
    mock_post = MagicMock(return_value=_response(502, text="upstream down"))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert results[0].data["error"] == "CrawlerData API error 502: Bad Gateway"


def test_crawlerdata_search_dataframe_shape(component):
    """The default output builds a DataFrame from the mapped results."""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        frame = component.crawlerdata_search()
    assert len(frame) == 3


def test_tool_mode_exposes_a_crawlerdata_specific_tool():
    """The agent-facing tool name must not collide with other search components."""
    # Tools read inputs the way a graph sets them (constructor kwargs), not
    # attributes assigned after construction, so build the component directly.
    component = CrawlerDataSearchComponent(
        crawlerdata_api_key="test-key",  # pragma: allowlist secret
        max_results=10,
    )
    tools = asyncio.run(component.to_toolkit())
    assert [tool.name for tool in tools] == ["crawlerdata_search"]

    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        output = asyncio.run(tools[0].ainvoke({"input_value": "langflow"}))
    assert mock_post.call_args.kwargs["json"]["params"]["query"] == "langflow"
    # The table stays narrow enough that the agent sees titles and snippets, not "..." columns.
    assert "Result one" in str(output)
