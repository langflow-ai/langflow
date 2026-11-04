"""Unit tests for the Keenable components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the
real endpoint selection, headers, payloads and error handling of the client.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.keenable.keenable_common import API_BASE_URL, APP_TITLE
from lfx_bundles.keenable.keenable_fetch import KeenableFetchComponent
from lfx_bundles.keenable.keenable_search import KeenableSearchComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-keenable-api-key-placeholder"  # pragma: allowlist secret

SEARCH_RESULTS = [
    {
        "title": "Langflow",
        "url": "https://www.langflow.org/",
        "description": "",
        "snippet": "Langflow is a low-code tool for building AI agents.",
    },
    {"title": "Only a title", "url": "https://example.com/", "description": "", "snippet": ""},
]


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _search(**values) -> KeenableSearchComponent:
    component = KeenableSearchComponent()
    component.set(**{"query": "langflow agents", **values})
    return component


def _fetch(**values) -> KeenableFetchComponent:
    component = KeenableFetchComponent()
    component.set(**{"url": "https://www.langflow.org/", **values})
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [KeenableSearchComponent, KeenableFetchComponent])
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [KeenableSearchComponent, KeenableFetchComponent])
def test_metadata(component_class: type[Component]) -> None:
    component = component_class()
    assert component.icon == "Keenable"
    assert "docs.keenable.ai" in component.documentation
    api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
    assert api_key.required is False


@pytest.mark.unit
class TestKeenableSearch:
    def test_keyless_search_uses_public_endpoint(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"results": SEARCH_RESULTS})) as request:
            data = _search().search()

        method, url = request.call_args.args
        assert method == "POST"
        assert url == f"{API_BASE_URL}/v1/search/public"
        headers = request.call_args.kwargs["headers"]
        assert headers["X-Keenable-Title"] == APP_TITLE
        assert "X-API-Key" not in headers
        assert request.call_args.kwargs["json"] == {"query": "langflow agents", "max_results": 5}
        assert [item.text for item in data] == [SEARCH_RESULTS[0]["snippet"], "Only a title"]
        assert data[0].data["url"] == "https://www.langflow.org/"

    def test_api_key_switches_to_keyed_endpoint(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"results": []})) as request:
            _search(api_key=f"  {API_KEY}  ").search()

        assert request.call_args.args[1] == f"{API_BASE_URL}/v1/search"
        assert request.call_args.kwargs["headers"]["X-API-Key"] == API_KEY

    def test_optional_filters_and_max_results_are_sent(self) -> None:
        component = _search(max_results=500, site=" docs.python.org ", published_after="2026-01-01")
        with patch("httpx.Client.request", return_value=_response(json_body={"results": []})) as request:
            component.search()

        assert request.call_args.kwargs["json"] == {
            "query": "langflow agents",
            "max_results": 50,
            "site": "docs.python.org",
            "published_after": "2026-01-01",
        }

    def test_empty_query_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _search(query="   ").search()

        request.assert_not_called()
        assert data[0].data["error"] == "Enter a search query."

    def test_rate_limit_error_is_returned_and_key_is_redacted(self) -> None:
        body = {"error": "Rate limit exceeded", "message": f"Too many requests for {API_KEY}"}
        with patch("httpx.Client.request", return_value=_response(429, json_body=body)):
            data = _search(api_key=API_KEY).search()

        error = data[0].data["error"]
        assert "rate limit exceeded (429)" in error
        assert API_KEY not in error

    def test_key_cut_at_the_detail_limit_is_still_redacted(self) -> None:
        # The key straddles the 300-character cap on the echoed detail.
        body = {"message": "x" * 290 + API_KEY}
        with patch("httpx.Client.request", return_value=_response(500, json_body=body)):
            data = _search(api_key=API_KEY).search()

        assert API_KEY[:10] not in data[0].data["error"]

    def test_non_json_response_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(text="<html>bad gateway</html>")):
            data = _search().search()

        assert "not JSON" in data[0].data["error"]

    def test_timeout_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ReadTimeout("slow")):
            data = _search(timeout=2.5).search()

        assert data[0].data["error"] == "Keenable request timed out after 2.5 seconds."

    def test_dataframe_output_has_one_row_per_result(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"results": SEARCH_RESULTS})):
            frame = _search().search_dataframe()

        assert len(frame) == len(SEARCH_RESULTS)
        assert list(frame["url"]) == [item["url"] for item in SEARCH_RESULTS]


@pytest.mark.unit
class TestKeenableFetch:
    def test_keyless_fetch_uses_public_endpoint(self) -> None:
        body = {"url": "https://www.langflow.org/", "title": "Langflow", "content": "# Langflow\n\nBuild agents."}
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            page = _fetch().fetch_page()

        method, url = request.call_args.args
        assert method == "GET"
        assert url == f"{API_BASE_URL}/v1/fetch/public"
        assert request.call_args.kwargs["params"] == {"url": "https://www.langflow.org/"}
        assert request.call_args.kwargs["headers"]["X-Keenable-Title"] == APP_TITLE
        assert page.text == body["content"]
        assert page.data["title"] == "Langflow"

    def test_api_key_switches_to_keyed_endpoint(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"content": ""})) as request:
            _fetch(api_key=API_KEY).fetch_page()

        assert request.call_args.args[1] == f"{API_BASE_URL}/v1/fetch"
        assert request.call_args.kwargs["headers"]["X-API-Key"] == API_KEY

    def test_live_fetch_is_sent_only_when_enabled(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"content": ""})) as request:
            _fetch(live=True).fetch_page()

        assert request.call_args.kwargs["params"] == {"url": "https://www.langflow.org/", "live": "true"}

    @pytest.mark.parametrize(
        "url", ["", "example.com", "file:///etc/passwd", "ftp://example.com/x", "https://[example"]
    )
    def test_rejects_non_http_urls_without_a_request(self, url: str) -> None:
        with patch("httpx.Client.request") as request:
            page = _fetch(url=url).fetch_page()

        request.assert_not_called()
        assert "absolute http(s) URL" in page.data["error"]

    def test_auth_error_is_returned(self) -> None:
        with patch("httpx.Client.request", return_value=_response(401, json_body={"error": "Invalid API key"})):
            page = _fetch(api_key=API_KEY).fetch_page()

        assert page.data["error"] == "Keenable rejected the API key (401): Invalid API key"

    def test_unreachable_api_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ConnectError("connection refused")):
            page = _fetch().fetch_page()

        assert page.data["error"].startswith("Could not reach the Keenable API: ConnectError")
