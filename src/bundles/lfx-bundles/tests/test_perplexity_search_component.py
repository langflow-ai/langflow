"""Unit tests for the Perplexity Search component (``lfx_bundles.perplexity``).

The component calls the Perplexity Search API with ``httpx``; the tests patch
``httpx.Client.post`` to return real ``httpx.Response`` objects, so no network
access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_bundles.perplexity import PerplexitySearchComponent
from lfx_bundles.perplexity.perplexity_search import INVALID_KEY_FORMAT_MESSAGE, REDACTED, SEARCH_URL

POST_PATCH_TARGET = "httpx.Client.post"

SAMPLE_PAYLOAD = {
    "id": "search-123",
    "results": [
        {
            "title": "Result one",
            "url": "https://example.com/one",
            "snippet": "First snippet.",
            "date": "2026-01-02",
            "last_updated": "2026-01-03",
        },
        {
            "title": "Result two",
            "url": "https://example.com/two",
            "snippet": "Second snippet.",
        },
    ],
}


def _response(status_code: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("POST", SEARCH_URL), **kwargs)


def _mock_post(payload: object) -> MagicMock:
    return MagicMock(return_value=_response(json=payload))


@pytest.fixture
def component() -> PerplexitySearchComponent:
    c = PerplexitySearchComponent()
    c.api_key = "test-key"  # pragma: allowlist secret
    c.query = "hello"
    c.max_results = 10
    c.search_type = "web"
    c.search_domain_filter = ""
    c.search_recency_filter = None
    return c


def test_component_metadata():
    """Class name and identifiers must stay stable for saved flows."""
    assert PerplexitySearchComponent.__name__ == "PerplexitySearchComponent"
    assert PerplexitySearchComponent.name == "PerplexitySearch"
    assert PerplexitySearchComponent.icon == "Perplexity"


def test_missing_api_key_raises(component):
    """No key set -> clear ValueError instead of an anonymous request."""
    component.api_key = ""
    with pytest.raises(ValueError, match="Perplexity API Key is required"):
        component._search()


def test_fetch_content_reports_missing_api_key_without_request(component):
    """The public output turns a missing key into an error row and never calls the API."""
    component.api_key = ""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    mock_post.assert_not_called()
    assert len(results) == 1
    assert "Perplexity API Key is required" in results[0].data["error"]


def test_missing_query_is_an_error_row(component):
    """An empty query never reaches the API."""
    component.query = "   "
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    mock_post.assert_not_called()
    assert "Search Query is required" in results[0].data["error"]


def test_search_sends_bearer_token_integration_headers_and_json_body(component):
    """The request is a POST to /search with Bearer auth and the Langflow attribution headers."""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.args[0] == SEARCH_URL
    headers = mock_post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"  # pragma: allowlist secret
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Pplx-Integration"] == "langflow"
    assert headers["User-Agent"] == "langflow-perplexity-bundle"
    assert mock_post.call_args.kwargs["json"] == {"query": "hello", "max_results": 10, "search_type": "web"}


def test_search_includes_optional_filters(component):
    """Domain and recency filters are sent only when set; domains are split and trimmed."""
    component.search_type = "fast"
    component.search_domain_filter = " wikipedia.org ,arxiv.org "
    component.search_recency_filter = "week"
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.kwargs["json"] == {
        "query": "hello",
        "max_results": 10,
        "search_type": "fast",
        "search_domain_filter": ["wikipedia.org", "arxiv.org"],
        "search_recency_filter": "week",
    }


def test_search_exclusion_domain_filter_keeps_prefix(component):
    """An exclusion-only filter keeps the '-' prefix the API expects (one mode per request)."""
    component.search_domain_filter = "-pinterest.com, -quora.com"
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.kwargs["json"]["search_domain_filter"] == ["-pinterest.com", "-quora.com"]


def test_too_many_domains_is_an_error_row(component):
    """The API accepts at most 20 domains; the component reports that before sending."""
    component.search_domain_filter = ",".join(f"site{i}.com" for i in range(21))
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    mock_post.assert_not_called()
    assert "at most 20 domains" in results[0].data["error"]


def test_max_results_is_clamped_high(component):
    """max_results above the range is clamped to the 20 upper bound."""
    component.max_results = 500
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.kwargs["json"]["max_results"] == 20


@pytest.mark.parametrize("value", [0, -5])
def test_max_results_is_clamped_low(component, value):
    """max_results at or below zero is clamped to the 1 lower bound, not replaced by the default."""
    component.max_results = value
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.kwargs["json"]["max_results"] == 1


def test_max_results_none_uses_default(component):
    """Only an unset max_results falls back to the default of 10."""
    component.max_results = None
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        component._search()
    assert mock_post.call_args.kwargs["json"]["max_results"] == 10


def test_max_results_range_spec_matches_clamp():
    """The UI range matches the bounds the request clamps to."""
    max_results = next(i for i in PerplexitySearchComponent.inputs if i.name == "max_results")
    assert max_results.range_spec is not None
    assert (max_results.range_spec.min, max_results.range_spec.max) == (1, 20)
    assert max_results.range_spec.step_type == "int"


def test_fetch_content_maps_results(component):
    """Results map to Data(text=snippet, data={title,url,snippet,date,last_updated})."""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 2
    assert results[0].text == "First snippet."
    assert results[0].data["title"] == "Result one"
    assert results[0].data["url"] == "https://example.com/one"
    assert results[0].data["date"] == "2026-01-02"
    assert results[0].data["last_updated"] == "2026-01-03"
    # date and last_updated are optional in the API response.
    assert results[1].data["date"] is None
    assert results[1].data["last_updated"] is None


def test_fetch_content_handles_empty_results(component):
    """A payload with no results yields an empty list, not an error."""
    mock_post = _mock_post({"id": "search-empty", "results": []})
    with patch(POST_PATCH_TARGET, mock_post):
        assert component.fetch_content() == []


def test_fetch_content_skips_malformed_results(component):
    """Result entries that are not JSON objects are skipped instead of crashing."""
    mock_post = _mock_post({"results": ["not-an-object", SAMPLE_PAYLOAD["results"][0]]})
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


def test_fetch_content_wraps_timeout(component):
    """A timeout is surfaced as a single error Data, not raised."""
    mock_post = MagicMock(side_effect=httpx.ReadTimeout("slow"))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 1
    assert "timed out" in results[0].data["error"]


def test_fetch_content_wraps_request_error_without_exception_text(component):
    """A transport error is surfaced as a single error Data that names the error type, not its text."""
    mock_post = MagicMock(side_effect=httpx.ConnectError("boom test-key"))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 1
    assert "ConnectError" in results[0].data["error"]
    assert "boom" not in results[0].data["error"]
    assert "test-key" not in results[0].data["error"]


def test_api_key_whitespace_is_stripped_before_building_headers(component):
    """A key pasted with a trailing newline is sent clean instead of producing an illegal header."""
    component.api_key = "pplx-trailing\n"  # pragma: allowlist secret
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer pplx-trailing"  # pragma: allowlist secret
    assert len(results) == 2


def test_malformed_api_key_never_reaches_error_row_or_log(component):
    """An embedded newline makes h11 reject the header; the key must not appear anywhere we surface."""
    malformed_key = "pplx-first\npplx-second"  # pragma: allowlist secret
    component.api_key = malformed_key

    def reject_like_h11(_url, *, headers, **_kwargs):
        # h11 rejects the header after connecting and echoes the raw value, exactly like this.
        msg = f"Illegal header value {headers['Authorization'].encode()!r}"
        raise httpx.LocalProtocolError(msg)

    mock_post = MagicMock(side_effect=reject_like_h11)
    with patch(POST_PATCH_TARGET, mock_post), patch("lfx_bundles.perplexity.perplexity_search.logger") as mock_logger:
        results = component.fetch_content()
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {malformed_key}"
    assert len(results) == 1
    assert results[0].data["error"] == INVALID_KEY_FORMAT_MESSAGE
    assert results[0].text == INVALID_KEY_FORMAT_MESSAGE
    logged = " ".join(str(call) for call in mock_logger.error.call_args_list)
    for fragment in (malformed_key, "pplx-first", "pplx-second"):
        assert fragment not in results[0].data["error"]
        assert fragment not in logged


def test_local_protocol_error_text_is_not_echoed(component):
    """Even if the transport raises with the key in the message, the row and log only carry the fixed text."""
    mock_post = MagicMock(side_effect=httpx.LocalProtocolError("Illegal header value b'Bearer test-key\\n'"))
    with patch(POST_PATCH_TARGET, mock_post), patch("lfx_bundles.perplexity.perplexity_search.logger") as mock_logger:
        results = component.fetch_content()
    assert results[0].data["error"] == INVALID_KEY_FORMAT_MESSAGE
    assert "test-key" not in " ".join(str(call) for call in mock_logger.error.call_args_list)


@pytest.mark.parametrize("status_code", [422, 500])
def test_error_bodies_that_echo_the_key_are_redacted(component, status_code):
    """Upstream 422 and 500 bodies may echo the request; the key is replaced before the row or log is written."""
    body = {"detail": "bad request with Authorization: Bearer test-key for query hello"}
    mock_post = MagicMock(return_value=_response(status_code, json=body))
    with patch(POST_PATCH_TARGET, mock_post), patch("lfx_bundles.perplexity.perplexity_search.logger") as mock_logger:
        results = component.fetch_content()
    error = results[0].data["error"]
    assert f"HTTP {status_code}" in error
    assert "test-key" not in error
    assert REDACTED in error
    assert results[0].text == error
    logged = " ".join(str(call) for call in mock_logger.error.call_args_list)
    assert "test-key" not in logged
    assert REDACTED in logged


def test_error_text_body_that_echoes_the_key_is_redacted(component):
    """A non-JSON 500 body is redacted the same way as a JSON one."""
    mock_post = MagicMock(return_value=_response(500, text="upstream saw Bearer test-key"))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert results[0].data["error"] == f"Perplexity Search API returned HTTP 500: upstream saw Bearer {REDACTED}"


def test_fetch_content_maps_401_to_invalid_key_message(component):
    """A 401 is reported as an API key problem."""
    mock_post = MagicMock(return_value=_response(401, json={"error": {"message": "Invalid API key"}}))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert len(results) == 1
    assert "HTTP 401" in results[0].data["error"]
    assert "Perplexity API Key" in results[0].data["error"]


def test_fetch_content_surfaces_422_validation_detail(component):
    """A 422 keeps the API's validation detail."""
    body = {"detail": [{"loc": ["body", "max_results"], "msg": "ensure this value is less than or equal to 20"}]}
    mock_post = MagicMock(return_value=_response(422, json=body))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert "HTTP 422" in results[0].data["error"]
    assert "less than or equal to 20" in results[0].data["error"]


def test_fetch_content_maps_429_to_rate_limit_message(component):
    """A 429 is reported as a rate limit."""
    mock_post = MagicMock(return_value=_response(429, text="Too Many Requests"))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert "HTTP 429" in results[0].data["error"]
    assert "rate limit" in results[0].data["error"]


def test_fetch_content_http_error_without_json_body(component):
    """A non-JSON error body falls back to the raw text."""
    mock_post = MagicMock(return_value=_response(502, text="upstream down"))
    with patch(POST_PATCH_TARGET, mock_post):
        results = component.fetch_content()
    assert results[0].data["error"] == "Perplexity Search API returned HTTP 502: upstream down"


def test_perplexity_search_dataframe_shape(component):
    """The default output builds a DataFrame from the mapped results."""
    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        frame = component.perplexity_search()
    assert len(frame) == 2
    assert {"title", "url", "snippet"} <= set(frame.columns)


def test_tool_mode_exposes_a_perplexity_specific_tool():
    """The agent-facing tool name must not collide with other search components."""
    # Tools read inputs the way a graph sets them (constructor kwargs), not
    # attributes assigned after construction, so build the component directly.
    component = PerplexitySearchComponent(api_key="test-key", max_results=10)  # pragma: allowlist secret
    tools = asyncio.run(component.to_toolkit())
    assert [tool.name for tool in tools] == ["perplexity_search"]

    mock_post = _mock_post(SAMPLE_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        output = asyncio.run(tools[0].ainvoke({"query": "langflow"}))
    assert mock_post.call_args.kwargs["json"] == {"query": "langflow", "max_results": 10, "search_type": "web"}
    assert "Result one" in str(output)
