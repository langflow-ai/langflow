"""Unit tests for the Piloterr components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the
real endpoint, headers, parameters and error handling of the client.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.piloterr.piloterr_common import API_BASE_URL
from lfx_bundles.piloterr.piloterr_google_search import PiloterrGoogleSearchComponent
from lfx_bundles.piloterr.piloterr_website_scraper import PiloterrWebsiteScraperComponent, html_to_text

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-piloterr-api-key-placeholder"  # pragma: allowlist secret

SEARCH_ROWS = [
    {
        "position": 1,
        "title": "Langflow",
        "link": "https://www.langflow.org/",
        "snippet": "Langflow is a low-code tool for building AI agents.",
    },
    {"position": 2, "title": "Only a title", "link": "https://example.com/"},
    "not an object",
]
PAGE = (
    "<!doctype html><html><head><title>Example  Domain</title><style>body{color:red}</style></head>"
    "<body><script>var x = 1;</script><h1>Example Domain</h1><p>This domain is for use in "
    "documentation examples.</p><ul><li>One</li><li>Two &amp; three</li></ul></body></html>"
)
COMPONENTS = [PiloterrGoogleSearchComponent, PiloterrWebsiteScraperComponent]


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _search(**values) -> PiloterrGoogleSearchComponent:
    component = PiloterrGoogleSearchComponent()
    component.set(**{"api_key": API_KEY, "query": "langflow agents", **values})
    return component


def _scraper(**values) -> PiloterrWebsiteScraperComponent:
    component = PiloterrWebsiteScraperComponent()
    component.set(**{"api_key": API_KEY, "url": "https://example.com/", **values})
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", COMPONENTS)
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", COMPONENTS)
def test_metadata(component_class: type[Component]) -> None:
    component = component_class()
    assert component.icon == "Piloterr"
    assert "docs.piloterr.com" in component.documentation
    api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
    assert api_key.required is True


@pytest.mark.unit
class TestPiloterrGoogleSearch:
    def test_search_sends_the_key_and_maps_rows(self) -> None:
        with patch(
            "httpx.Client.request", return_value=_response(json_body={"organic_results": SEARCH_ROWS})
        ) as request:
            data = _search(api_key=f"  {API_KEY}  ").search()

        method, url = request.call_args.args
        assert method == "GET"
        assert url == f"{API_BASE_URL}/v2/google/search"
        assert request.call_args.kwargs["headers"]["x-api-key"] == API_KEY
        assert request.call_args.kwargs["params"] == {"query": "langflow agents", "num": 10}
        assert [item.text for item in data] == [SEARCH_ROWS[0]["snippet"], "Only a title"]

    def test_optional_parameters_are_sent(self) -> None:
        component = _search(max_results=500, country=" FR ", language="fr", location="Paris, France")
        with patch("httpx.Client.request", return_value=_response(json_body={"organic_results": []})) as request:
            component.search()

        assert request.call_args.kwargs["params"] == {
            "query": "langflow agents",
            "num": 100,
            "gl": "fr",
            "hl": "fr",
            "location": "Paris, France",
        }

    def test_missing_organic_results_is_an_empty_search(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={})):
            assert _search().search() == []

    def test_non_list_organic_results_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"organic_results": {"a": 1}})):
            assert "not a list" in _search().search()[0].data["error"]

    def test_empty_query_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _search(query=" ").search()

        request.assert_not_called()
        assert data[0].data["error"] == "Enter a search query."

    def test_missing_key_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _search(api_key="").search()

        request.assert_not_called()
        assert data[0].data["error"] == "Enter a Piloterr API key."

    def test_rate_limit_answered_as_401_is_labelled_as_a_rate_limit(self) -> None:
        body = {"error": {"code": "rate_limit", "message": f"Rate limit exceeded for {API_KEY}"}}
        with patch("httpx.Client.request", return_value=_response(401, json_body=body)):
            error = _search().search()[0].data["error"]

        assert error.startswith("Piloterr rate limit exceeded (401)")
        assert API_KEY not in error

    def test_invalid_key_error_is_returned(self) -> None:
        with patch("httpx.Client.request", return_value=_response(401, json_body={"error": "Invalid API key"})):
            assert _search().search()[0].data["error"] == "Piloterr rejected the API key (401): Invalid API key"

    def test_non_json_response_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(text="<html>bad gateway</html>")):
            assert "not JSON" in _search().search()[0].data["error"]

    def test_timeout_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ReadTimeout("slow")):
            data = _search(timeout=3).search()

        assert data[0].data["error"] == "Piloterr request timed out after 3 seconds."

    def test_dataframe_output_has_one_row_per_result(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"organic_results": SEARCH_ROWS})):
            frame = _search().search_dataframe()

        assert list(frame["link"]) == ["https://www.langflow.org/", "https://example.com/"]


@pytest.mark.unit
class TestPiloterrWebsiteScraper:
    def test_crawler_returns_readable_text_and_html(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body=PAGE)) as request:
            page = _scraper().fetch_page()

        assert request.call_args.args[1] == f"{API_BASE_URL}/v2/website/crawler"
        assert request.call_args.kwargs["params"] == {"query": "https://example.com/"}
        assert page.text == "Example Domain\nThis domain is for use in documentation examples.\nOne\nTwo & three"
        assert page.data["title"] == "Example Domain"
        assert page.data["engine"] == "crawler"
        assert page.data["html"] == PAGE

    def test_raw_html_body_is_accepted(self) -> None:
        with patch("httpx.Client.request", return_value=_response(text=PAGE)):
            page = _scraper().fetch_page()

        assert page.data["title"] == "Example Domain"

    def test_rendering_engine_sends_the_capped_wait(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body=PAGE)) as request:
            _scraper(engine="Rendering", wait_in_seconds=99).fetch_page()

        assert request.call_args.args[1] == f"{API_BASE_URL}/v2/website/rendering"
        assert request.call_args.kwargs["params"] == {"query": "https://example.com/", "wait_in_seconds": 30}

    def test_wait_is_ignored_outside_rendering(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body=PAGE)) as request:
            _scraper(engine="Web Unlocker", wait_in_seconds=5).fetch_page()

        assert request.call_args.args[1] == f"{API_BASE_URL}/v2/website/webunlocker"
        assert request.call_args.kwargs["params"] == {"query": "https://example.com/"}

    @pytest.mark.parametrize("body", [{"html": "<p>x</p>"}, ["a"], 3])
    def test_non_string_json_is_an_error(self, body: Any) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body=body)):
            page = _scraper().fetch_page()

        assert "expected the page HTML" in page.data["error"]

    @pytest.mark.parametrize(
        "url", ["", "example.com", "file:///etc/passwd", "ftp://example.com/x", "https://[example"]
    )
    def test_rejects_non_http_urls_without_a_request(self, url: str) -> None:
        with patch("httpx.Client.request") as request:
            page = _scraper(url=url).fetch_page()

        request.assert_not_called()
        assert "absolute http(s) URL" in page.data["error"]

    def test_unreachable_api_is_an_error_without_the_key(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ConnectError(f"refused {API_KEY}")):
            page = _scraper().fetch_page()

        assert page.data["error"].startswith("Could not reach the Piloterr API: ConnectError")
        assert API_KEY not in page.data["error"]

    def test_server_error_is_returned(self) -> None:
        with patch("httpx.Client.request", return_value=_response(502, text="upstream failed")):
            page = _scraper().fetch_page()

        assert page.data["error"] == "Piloterr API error (502): upstream failed"


@pytest.mark.unit
def test_html_to_text_skips_scripts_and_keeps_blocks() -> None:
    title, text = html_to_text(
        "<html><head><title> T </title></head><body><div>a</div><noscript>x</noscript>b</body></html>"
    )
    assert title == "T"
    assert text == "a\nb"
