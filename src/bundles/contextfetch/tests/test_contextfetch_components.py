"""Unit tests for the ContextFetch extension bundle (``lfx-contextfetch``).

The components call the ContextFetch API with ``httpx``; the tests patch
``httpx.post`` in the shared helper module to return real ``httpx.Response``
objects, so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_contextfetch import ContextFetchContentsComponent, ContextFetchSearchComponent

POST_PATCH_TARGET = "lfx_contextfetch.components.contextfetch._common.httpx.post"
SEARCH_URL = "https://api.contextfetch.dev/v1/search"
CONTENTS_URL = "https://api.contextfetch.dev/v1/contents"

SEARCH_PAYLOAD = {
    "requestId": "abc",
    "results": [
        {
            "url": "https://example.com/one",
            "title": "Result one",
            "publishedDate": "2026-01-02",
            "text": None,
            "highlights": ["First chunk.", "Second chunk."],
            "prunedContext": "Pruned one.",
        },
        {"url": "https://example.com/two", "title": "Result two", "prunedContext": "Pruned two."},
    ],
    "costDollars": {"total": 0.001},
}

CONTENTS_PAYLOAD = {
    "results": [{"url": "https://example.com/", "title": "Example", "text": "# Example\n\nBody."}],
    "statuses": [
        {"id": "https://example.com/", "status": "success"},
        {"id": "https://example.com/missing", "status": "error", "error": {"tag": "CRAWL_NOT_FOUND", "message": "404"}},
    ],
}


def _response(status_code: int = 200, url: str = SEARCH_URL, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("POST", url), **kwargs)


def _mock_post(payload: object, url: str = SEARCH_URL) -> MagicMock:
    return MagicMock(return_value=_response(url=url, json=payload))


@pytest.fixture
def search() -> ContextFetchSearchComponent:
    c = ContextFetchSearchComponent()
    c.input_value = "hello"
    c.contextfetch_api_key = "test-key"  # pragma: allowlist secret
    c.max_results = 5
    c.content = "Pruned Context"
    c.include_domains = ""
    c.exclude_domains = ""
    c.start_published_date = ""
    return c


@pytest.fixture
def contents() -> ContextFetchContentsComponent:
    c = ContextFetchContentsComponent()
    c.urls = "https://example.com/"
    c.contextfetch_api_key = "test-key"  # pragma: allowlist secret
    c.highlights_query = ""
    return c


def test_class_names_are_stable():
    """Class names must stay stable for saved flows."""
    assert ContextFetchSearchComponent.__name__ == "ContextFetchSearchComponent"
    assert ContextFetchContentsComponent.__name__ == "ContextFetchContentsComponent"


def test_search_missing_api_key_makes_no_request(search):
    search.contextfetch_api_key = ""
    mock_post = _mock_post(SEARCH_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        results = search.fetch_content()
    mock_post.assert_not_called()
    assert "ContextFetch API key is required" in results[0].data["error"]


def test_search_sends_bearer_auth_and_default_body(search):
    mock_post = _mock_post(SEARCH_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        search.fetch_content()
    assert mock_post.call_args.args[0] == SEARCH_URL
    headers = mock_post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["User-Agent"] == "langflow-contextfetch-bundle"
    assert mock_post.call_args.kwargs["json"] == {
        "query": "hello",
        "numResults": 5,
        "contents": {"prunedContext": True, "highlights": False, "text": False},
    }


def test_search_sends_filters_and_clamps_results(search):
    search.max_results = 500
    search.content = "Full Text"
    search.include_domains = "a.com, b.org\nc.net"
    search.exclude_domains = "spam.com"
    search.start_published_date = " 2026-01-01 "
    mock_post = _mock_post(SEARCH_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        search.fetch_content()
    body = mock_post.call_args.kwargs["json"]
    assert body["numResults"] == 25
    assert body["contents"] == {"prunedContext": False, "highlights": False, "text": True}
    assert body["includeDomains"] == ["a.com", "b.org", "c.net"]
    assert body["excludeDomains"] == ["spam.com"]
    assert body["startPublishedDate"] == "2026-01-01"


def test_search_maps_results(search):
    with patch(POST_PATCH_TARGET, _mock_post(SEARCH_PAYLOAD)):
        results = search.fetch_content()
    assert [r.text for r in results] == ["Pruned one.", "Pruned two."]
    assert results[0].data["title"] == "Result one"
    assert results[0].data["url"] == "https://example.com/one"
    assert results[0].data["published_date"] == "2026-01-02"
    assert results[0].data["content"] == "Pruned one."


def test_search_joins_highlights(search):
    search.content = "Highlights"
    with patch(POST_PATCH_TARGET, _mock_post(SEARCH_PAYLOAD)):
        results = search.fetch_content()
    assert results[0].text == "First chunk.\n\nSecond chunk."
    assert results[1].text == ""


def test_search_rejects_non_object_payload(search):
    with patch(POST_PATCH_TARGET, _mock_post(["unexpected"])):
        results = search.fetch_content()
    assert "unexpected response" in results[0].data["error"]


def test_search_wraps_transport_error(search):
    with patch(POST_PATCH_TARGET, MagicMock(side_effect=httpx.HTTPError("boom"))):
        results = search.fetch_content()
    assert results[0].data["error"] == "boom"


def test_401_keeps_api_code_and_points_to_free_key(search):
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response(401, json={"error": "invalid_api_key"}))):
        results = search.fetch_content()
    error = results[0].data["error"]
    assert error.startswith("ContextFetch API error 401: invalid_api_key.")
    assert "contextfetch.dev/docs" in error


def test_402_uses_api_message(search):
    body = {"error": "insufficient_credits", "message": "Credits ran out."}
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response(402, json=body))):
        results = search.fetch_content()
    assert results[0].data["error"] == "ContextFetch API error 402: Credits ran out."


def test_422_lists_the_invalid_fields(search):
    body = {"detail": [{"loc": ["body", "numResults"], "msg": "Input should be a valid integer"}]}
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response(422, json=body))):
        results = search.fetch_content()
    assert results[0].data["error"] == "ContextFetch API error 422: numResults: Input should be a valid integer"


def test_error_without_json_body_uses_reason_phrase(search):
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response(502, text="upstream down"))):
        results = search.fetch_content()
    assert results[0].data["error"] == "ContextFetch API error 502: Bad Gateway"


def test_contents_splits_urls_and_sends_highlights(contents):
    contents.urls = "https://a.com/x?a=1,2, https://b.com\nhttps://c.com"
    contents.highlights_query = "pricing"
    mock_post = _mock_post(CONTENTS_PAYLOAD, CONTENTS_URL)
    with patch(POST_PATCH_TARGET, mock_post):
        contents.fetch_content()
    assert mock_post.call_args.args[0] == CONTENTS_URL
    assert mock_post.call_args.kwargs["json"] == {
        "urls": ["https://a.com/x?a=1,2", "https://b.com", "https://c.com"],
        "text": True,
        "highlights": {"query": "pricing"},
    }


def test_contents_maps_pages_and_failed_urls(contents):
    with patch(POST_PATCH_TARGET, _mock_post(CONTENTS_PAYLOAD, CONTENTS_URL)):
        results = contents.fetch_content()
    assert results[0].text == "# Example\n\nBody."
    assert results[0].data["url"] == "https://example.com/"
    assert results[1].data["url"] == "https://example.com/missing"
    assert results[1].data["error"] == "404"


def test_contents_without_urls_makes_no_request(contents):
    contents.urls = "  "
    mock_post = _mock_post(CONTENTS_PAYLOAD, CONTENTS_URL)
    with patch(POST_PATCH_TARGET, mock_post):
        results = contents.fetch_content()
    mock_post.assert_not_called()
    assert results[0].data["error"] == "At least one URL is required."


def test_tool_mode_exposes_contextfetch_specific_tools():
    """Agent-facing tool names must not collide with other search components."""
    search = ContextFetchSearchComponent(contextfetch_api_key="test-key", max_results=3)  # pragma: allowlist secret
    tools = asyncio.run(search.to_toolkit())
    assert [tool.name for tool in tools] == ["contextfetch_search"]
    mock_post = _mock_post(SEARCH_PAYLOAD)
    with patch(POST_PATCH_TARGET, mock_post):
        output = asyncio.run(tools[0].ainvoke({"input_value": "langflow"}))
    assert mock_post.call_args.kwargs["json"]["query"] == "langflow"
    assert "Result one" in str(output)

    contents = ContextFetchContentsComponent(contextfetch_api_key="test-key")  # pragma: allowlist secret
    tools = asyncio.run(contents.to_toolkit())
    assert [tool.name for tool in tools] == ["contextfetch_get_contents"]
