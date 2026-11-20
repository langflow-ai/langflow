"""Unit tests for the Clawifi components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the
real URL, headers, payloads and error handling of the client. No test contacts
the Clawifi API or needs a real API key.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.clawifi.clawifi_common import API_BASE_URL
from lfx_bundles.clawifi.clawifi_fetch import ClawifiFetchComponent
from lfx_bundles.clawifi.clawifi_search import ClawifiSearchComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-clawifi-api-key-placeholder"  # pragma: allowlist secret

SEARCH_RESULTS = [
    {
        "url": "https://modelcontextprotocol.io/",
        "title": "Model Context Protocol",
        "snippet": "An open protocol that connects AI applications to data and tools.",
        "rank": 1,
        "provider": "engine_a",
        "published_at": None,
        "modified_at": None,
        "data": {"engines": ["engine_a"]},
    },
    {
        "url": "https://example.com/",
        "title": "Only a title",
        "snippet": None,
        "rank": 2,
        "provider": "engine_b",
        "data": {},
    },
]

PAGE = {
    "url": "https://example.com/",
    "title": "Example Domain",
    "excerpt": "This domain is for use in documentation examples.",
    "language": "en",
    "published_at": None,
    "content_markdown": "# Example Domain\n\nThis domain is for use in documentation examples.",
    "content_text": "Example Domain This domain is for use in documentation examples.",
    "source_url": "https://example.com/",
}


def _response(
    status_code: int = 200,
    *,
    json_body: Any = None,
    text: str | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("POST", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, headers=headers, request=request)
    return httpx.Response(status_code, json=json_body, headers=headers, request=request)


def _search_body(results: list[dict[str, Any]] | None = None, **fields: Any) -> dict[str, Any]:
    return {"success": True, "query": "mcp", "results": SEARCH_RESULTS if results is None else results, **fields}


def _fetch_body(data: dict[str, Any] | None = None, **fields: Any) -> dict[str, Any]:
    return {
        "success": True,
        "content_status": "ok",
        "data": PAGE if data is None else data,
        "errors": [],
        **fields,
    }


def _search(**values: Any) -> ClawifiSearchComponent:
    component = ClawifiSearchComponent()
    component.set(**{"api_key": API_KEY, "query": "what is the model context protocol", **values})
    return component


def _fetch(**values: Any) -> ClawifiFetchComponent:
    component = ClawifiFetchComponent()
    component.set(**{"api_key": API_KEY, "url": "https://example.com/", **values})
    return component


@pytest.mark.unit
class TestClawifiSearchComponent:
    def test_metadata(self) -> None:
        component = ClawifiSearchComponent()
        assert component.icon == "Clawifi"
        assert component.documentation.startswith("https://clawifi.dev/docs")
        api_key = next(inp for inp in ClawifiSearchComponent.inputs if inp.name == "api_key")
        assert api_key.required is True

    def test_input_names_do_not_shadow_component_attributes(self) -> None:
        shadowed = [inp.name for inp in ClawifiSearchComponent.inputs if hasattr(Component, inp.name)]
        assert not shadowed

    def test_frontend_node_lists_the_inputs(self) -> None:
        node = ClawifiSearchComponent().to_frontend_node()["data"]["node"]
        assert node["display_name"] == "Clawifi Search"
        assert {"api_key", "query", "max_results", "include_domains", "exclude_domains", "time_range"} <= set(
            node["template"]
        )

    async def test_tool_mode_exposes_query_and_filters(self) -> None:
        tools = await ClawifiSearchComponent().to_toolkit()
        properties = tools[0].args_schema.model_json_schema()["properties"]
        assert {"query", "include_domains", "exclude_domains", "time_range"} <= set(properties)
        assert "api_key" not in properties

    def test_search_posts_query_with_bearer_key(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body=_search_body())) as request:
            data = _search().search()

        method, url = request.call_args.args
        assert method == "POST"
        assert url == f"{API_BASE_URL}/search/free"
        assert request.call_args.kwargs["headers"] == {"Authorization": f"Bearer {API_KEY}"}
        assert request.call_args.kwargs["json"] == {"query": "what is the model context protocol", "max_results": 5}
        assert [item.text for item in data] == [SEARCH_RESULTS[0]["snippet"], "Only a title"]
        assert data[0].data["url"] == "https://modelcontextprotocol.io/"
        assert "published_at" not in data[0].data

    def test_optional_filters_are_sent(self) -> None:
        component = _search(
            max_results=0,
            include_domains=" docs.python.org, peps.python.org ",
            exclude_domains="example.com\nexample.org",
            time_range="week",
        )
        with patch("httpx.Client.request", return_value=_response(json_body=_search_body([]))) as request:
            component.search()

        assert request.call_args.kwargs["json"] == {
            "query": "what is the model context protocol",
            "max_results": 1,
            "include_domains": ["docs.python.org", "peps.python.org"],
            "exclude_domains": ["example.com", "example.org"],
            "time_range": "week",
        }

    def test_any_time_range_is_not_sent(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body=_search_body([]))) as request:
            _search(time_range="any").search()

        assert "time_range" not in request.call_args.kwargs["json"]

    def test_empty_query_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _search(query="   ").search()

        request.assert_not_called()
        assert data[0].data["error"] == "Enter a search query."

    def test_missing_api_key_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _search(api_key="  ").search()

        request.assert_not_called()
        assert data[0].data["error"].startswith("Enter a Clawifi API key.")

    def test_failed_search_returns_the_engine_errors(self) -> None:
        body = _search_body(
            [],
            success=False,
            errors=[{"code": "provider_error", "message": "engine timed out"}, {"code": "rate_limited"}],
        )
        with patch("httpx.Client.request", return_value=_response(json_body=body)):
            data = _search().search()

        assert data[0].data["error"] == "Clawifi search failed: engine timed out; rate_limited"

    def test_key_is_redacted_from_a_failed_search_response(self) -> None:
        body = _search_body([], success=False, errors=[{"code": "provider_error", "message": f"bad token {API_KEY}"}])
        component = _search()
        with (
            patch("httpx.Client.request", return_value=_response(json_body=body)),
            patch("lfx_bundles.clawifi.clawifi_search.logger") as log,
        ):
            data = component.search()

        assert data[0].data["error"] == "Clawifi search failed: bad token ***"
        assert API_KEY not in str(data[0].data)
        assert API_KEY not in str(component.status)
        assert all(API_KEY not in str(call) for call in log.mock_calls)

    def test_response_without_results_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"success": True})):
            data = _search().search()

        assert "without a results list" in data[0].data["error"]

    def test_invalid_key_error_is_returned(self) -> None:
        body = {"detail": "Invalid API key", "error": {"code": "http_error", "message": "Invalid API key"}}
        with patch("httpx.Client.request", return_value=_response(401, json_body=body)):
            data = _search().search()

        assert data[0].data["error"] == "Clawifi rejected the API key (401): Invalid API key"

    def test_plan_required_error_names_the_code(self) -> None:
        body = {"detail": "Upgrade", "error": {"code": "plan_required", "message": "This feature needs a paid plan"}}
        with patch("httpx.Client.request", return_value=_response(403, json_body=body)):
            data = _search().search()

        assert data[0].data["error"] == (
            "Clawifi refused the request (403): This feature needs a paid plan (plan_required)"
        )

    def test_rate_limit_error_includes_retry_after(self) -> None:
        body = {"detail": "Too many requests", "error": {"code": "rate_limited", "message": "Too many requests"}}
        with patch(
            "httpx.Client.request",
            return_value=_response(429, json_body=body, headers={"Retry-After": "12"}),
        ):
            data = _search().search()

        error = data[0].data["error"]
        assert error == "Clawifi rate limit exceeded (429): Too many requests (rate_limited). Retry after 12 seconds."

    def test_validation_error_detail_list_is_readable(self) -> None:
        body = {"detail": [{"loc": ["body", "query"], "msg": "Field required", "type": "missing"}]}
        with patch("httpx.Client.request", return_value=_response(422, json_body=body)):
            data = _search().search()

        assert data[0].data["error"] == "Clawifi API error (422): Field required"

    def test_key_is_redacted_from_errors_even_when_cut_at_the_limit(self) -> None:
        # The key straddles the 300-character cap on the echoed detail.
        body = {"detail": "x" * 290 + API_KEY}
        with patch("httpx.Client.request", return_value=_response(500, json_body=body)):
            data = _search().search()

        assert API_KEY[:10] not in data[0].data["error"]

    def test_non_json_response_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(text="<html>bad gateway</html>")):
            data = _search().search()

        assert "not JSON" in data[0].data["error"]

    def test_timeout_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ReadTimeout("slow")):
            data = _search(timeout=2.5).search()

        assert data[0].data["error"] == "Clawifi request timed out after 2.5 seconds."

    def test_unreachable_api_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ConnectError("connection refused")):
            data = _search().search()

        assert data[0].data["error"].startswith("Could not reach the Clawifi API: ConnectError")

    def test_dataframe_output_has_one_row_per_result(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body=_search_body())):
            frame = _search().search_dataframe()

        assert len(frame) == len(SEARCH_RESULTS)
        assert list(frame["url"]) == [item["url"] for item in SEARCH_RESULTS]


@pytest.mark.unit
class TestClawifiFetchComponent:
    def test_metadata(self) -> None:
        component = ClawifiFetchComponent()
        assert component.icon == "Clawifi"
        assert component.documentation.startswith("https://clawifi.dev/docs")
        api_key = next(inp for inp in ClawifiFetchComponent.inputs if inp.name == "api_key")
        assert api_key.required is True

    def test_input_names_do_not_shadow_component_attributes(self) -> None:
        shadowed = [inp.name for inp in ClawifiFetchComponent.inputs if hasattr(Component, inp.name)]
        assert not shadowed

    def test_frontend_node_lists_the_inputs(self) -> None:
        node = ClawifiFetchComponent().to_frontend_node()["data"]["node"]
        assert node["display_name"] == "Clawifi Fetch"
        assert {"api_key", "url", "query", "top_k", "render", "content_scope"} <= set(node["template"])

    async def test_tool_mode_exposes_url_and_query(self) -> None:
        tools = await ClawifiFetchComponent().to_toolkit()
        properties = tools[0].args_schema.model_json_schema()["properties"]
        assert {"url", "query"} <= set(properties)
        assert "api_key" not in properties

    def test_fetch_posts_only_the_url_by_default(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body=_fetch_body())) as request:
            page = _fetch().fetch_page()

        method, url = request.call_args.args
        assert method == "POST"
        assert url == f"{API_BASE_URL}/fetch"
        assert request.call_args.kwargs["headers"] == {"Authorization": f"Bearer {API_KEY}"}
        assert request.call_args.kwargs["json"] == {"url": "https://example.com/"}
        assert page.text == PAGE["content_markdown"]
        assert page.data["title"] == "Example Domain"
        assert page.data["content_status"] == "ok"
        assert page.data["entity_type"] == "WebDocument"
        assert page.data["content_markdown"] == PAGE["content_markdown"]
        assert "published_at" not in page.data
        assert "content_text" not in page.data

    def test_query_sends_query_and_clamped_top_k(self) -> None:
        passages = {**PAGE, "content_markdown": "This domain is for use in documentation examples."}
        with patch("httpx.Client.request", return_value=_response(json_body=_fetch_body(passages))) as request:
            page = _fetch(query=" what is this domain for? ", top_k=50).fetch_page()

        assert request.call_args.kwargs["json"] == {
            "url": "https://example.com/",
            "query": "what is this domain for?",
            "top_k": 20,
        }
        assert page.text == passages["content_markdown"]
        assert page.data["query"] == "what is this domain for?"

    def test_top_k_is_not_sent_without_a_query(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body=_fetch_body())) as request:
            _fetch(top_k=3).fetch_page()

        assert "top_k" not in request.call_args.kwargs["json"]

    def test_render_and_content_scope_are_sent_when_changed(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body=_fetch_body())) as request:
            _fetch(render="auto", content_scope="full").fetch_page()

        assert request.call_args.kwargs["json"] == {
            "url": "https://example.com/",
            "render": "auto",
            "content_scope": "full",
        }

    def test_thin_page_is_returned_with_its_status(self) -> None:
        thin = {"url": "https://example.com/", "title": "Example Domain", "content_markdown": "# Example Domain"}
        with patch("httpx.Client.request", return_value=_response(json_body=_fetch_body(thin, content_status="thin"))):
            page = _fetch().fetch_page()

        assert page.text == "# Example Domain"
        assert page.data["content_status"] == "thin"
        assert "error" not in page.data

    @pytest.mark.parametrize(
        ("content_status", "hint"),
        [
            ("needs_javascript", "Set Render to auto"),
            ("blocked", "The site blocked the read."),
            ("not_found", "The page was not found."),
        ],
    )
    def test_unreadable_page_is_an_error(self, content_status: str, hint: str) -> None:
        body = _fetch_body({"url": "https://example.com/", "content_markdown": ""}, content_status=content_status)
        with patch("httpx.Client.request", return_value=_response(json_body=body)):
            page = _fetch().fetch_page()

        error = page.data["error"]
        assert f"(content_status: {content_status})" in error
        assert hint in error

    def test_record_read_through_an_official_api_is_passed_through(self) -> None:
        record = {"title": "A paper", "abstract": "We study agents.", "authors": ["A. Author"], "doi": None}
        body = _fetch_body(record, entity_type="Paper")
        with patch("httpx.Client.request", return_value=_response(json_body=body)):
            page = _fetch(url="https://arxiv.org/abs/0000.00000").fetch_page()

        assert "error" not in page.data
        assert page.data["entity_type"] == "Paper"
        assert page.data["abstract"] == "We study agents."
        assert "doi" not in page.data
        assert "We study agents." in page.text

    def test_empty_page_is_an_error(self) -> None:
        body = _fetch_body({"url": "https://example.com/", "content_markdown": ""})
        with patch("httpx.Client.request", return_value=_response(json_body=body)):
            page = _fetch().fetch_page()

        assert page.data["error"] == "Clawifi returned no content for https://example.com/."

    def test_empty_official_api_record_is_an_error(self) -> None:
        body = _fetch_body({"title": None, "doi": None}, entity_type="Paper")
        with patch("httpx.Client.request", return_value=_response(json_body=body)):
            page = _fetch(url="https://arxiv.org/abs/0000.00000").fetch_page()

        assert page.data["error"] == "Clawifi returned no content for https://arxiv.org/abs/0000.00000."

    def test_key_is_redacted_from_a_failed_read_response(self) -> None:
        body = _fetch_body({}, success=False, errors=[{"code": "fetch_failed", "message": f"echo {API_KEY}"}])
        body.pop("content_status")
        component = _fetch()
        with (
            patch("httpx.Client.request", return_value=_response(json_body=body)),
            patch("lfx_bundles.clawifi.clawifi_fetch.logger") as log,
        ):
            page = component.fetch_page()

        assert page.data["error"] == "Clawifi could not read https://example.com/. echo ***"
        assert API_KEY not in page.text
        assert API_KEY not in str(component.status)
        assert all(API_KEY not in str(call) for call in log.mock_calls)

    def test_failed_read_returns_the_errors(self) -> None:
        body = _fetch_body({}, success=False, errors=[{"code": "fetch_failed", "message": "TLS handshake failed"}])
        body.pop("content_status")
        with patch("httpx.Client.request", return_value=_response(json_body=body)):
            page = _fetch().fetch_page()

        assert page.data["error"] == "Clawifi could not read https://example.com/. TLS handshake failed"

    @pytest.mark.parametrize(
        "url", ["", "example.com", "file:///etc/passwd", "ftp://example.com/x", "https://[example"]
    )
    def test_rejects_non_http_urls_without_a_request(self, url: str) -> None:
        with patch("httpx.Client.request") as request:
            page = _fetch(url=url).fetch_page()

        request.assert_not_called()
        assert "absolute http(s) URL" in page.data["error"]

    def test_long_query_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            page = _fetch(query="x" * 501).fetch_page()

        request.assert_not_called()
        assert "longer than 500 characters" in page.data["error"]

    def test_missing_api_key_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            page = _fetch(api_key="").fetch_page()

        request.assert_not_called()
        assert page.data["error"].startswith("Enter a Clawifi API key.")

    def test_out_of_credits_error_is_returned(self) -> None:
        body = {
            "detail": "Insufficient Clawifi credits: needed 1, balance 0",
            "error": {"code": "http_error", "message": "Insufficient Clawifi credits: needed 1, balance 0"},
        }
        with patch("httpx.Client.request", return_value=_response(402, json_body=body)):
            page = _fetch().fetch_page()

        assert page.data["error"] == (
            "Not enough Clawifi credits for this call (402): Insufficient Clawifi credits: needed 1, balance 0"
        )
