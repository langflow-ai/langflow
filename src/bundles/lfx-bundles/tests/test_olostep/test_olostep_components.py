"""Unit tests for the Olostep components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the
real endpoints, headers, payloads and error handling of the client.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.olostep.olostep_answer import OlostepAnswerComponent
from lfx_bundles.olostep.olostep_common import API_BASE_URL
from lfx_bundles.olostep.olostep_crawl import _MAX_PAGE_REQUESTS, OlostepCrawlComponent
from lfx_bundles.olostep.olostep_map import MAX_CURSOR_PAGES, OlostepMapComponent
from lfx_bundles.olostep.olostep_scrape import OlostepScrapeComponent
from lfx_bundles.olostep.olostep_search import OlostepSearchComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-olostep-api-key-placeholder"  # pragma: allowlist secret

ALL_COMPONENTS = [
    OlostepSearchComponent,
    OlostepScrapeComponent,
    OlostepAnswerComponent,
    OlostepMapComponent,
    OlostepCrawlComponent,
]

SEARCH_LINKS = [
    {"url": "https://www.langflow.org/", "title": "Langflow", "description": "Build AI agents visually."},
    {"url": "https://example.com/", "title": "Only a title", "description": ""},
]


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _make(component_class: type[Component], **values) -> Any:
    component = component_class()
    component.set(**{"api_key": API_KEY, **values})
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_metadata(component_class: type[Component]) -> None:
    component = component_class()
    assert component.icon == "Olostep"
    assert component.documentation.startswith("https://docs.olostep.com")
    api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
    assert api_key.required is True


@pytest.mark.unit
def test_missing_api_key_makes_no_request() -> None:
    with patch("httpx.Client.request") as request:
        data = _make(OlostepSearchComponent, api_key="  ", query="langflow").search()

    request.assert_not_called()
    assert "Enter an Olostep API key" in data[0].data["error"]


@pytest.mark.unit
class TestOlostepSearch:
    def test_search_sends_query_and_bearer_key(self) -> None:
        body = {"id": "search_1", "result": {"links": SEARCH_LINKS}}
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            data = _make(OlostepSearchComponent, query="langflow agents").search()

        method, url = request.call_args.args
        assert method == "POST"
        assert url == f"{API_BASE_URL}/v1/searches"
        assert request.call_args.kwargs["headers"]["Authorization"] == f"Bearer {API_KEY}"
        assert request.call_args.kwargs["json"] == {"query": "langflow agents", "limit": 5}
        assert [item.text for item in data] == ["Build AI agents visually.", "Only a title"]
        assert data[0].data["url"] == "https://www.langflow.org/"

    def test_filters_limit_and_scrape_options_are_sent(self) -> None:
        component = _make(
            OlostepSearchComponent,
            query="langflow agents",
            limit=100,
            include_domains=" docs.langflow.org, github.com ",
            exclude_domains="pinterest.com",
            scrape_results=True,
        )
        with patch("httpx.Client.request", return_value=_response(json_body={"result": {"links": []}})) as request:
            component.search()

        assert request.call_args.kwargs["json"] == {
            "query": "langflow agents",
            "limit": 25,
            "include_domains": ["docs.langflow.org", "github.com"],
            "exclude_domains": ["pinterest.com"],
            "scrape_options": {"formats": ["markdown"]},
        }

    def test_scraped_markdown_is_the_row_text(self) -> None:
        links = [{"url": "https://example.com/", "title": "Example", "markdown_content": "# Example"}]
        with patch("httpx.Client.request", return_value=_response(json_body={"result": {"links": links}})):
            data = _make(OlostepSearchComponent, query="example").search()

        assert data[0].text == "# Example"

    def test_empty_query_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _make(OlostepSearchComponent, query="   ").search()

        request.assert_not_called()
        assert data[0].data["error"] == "Enter a search query."

    def test_rate_limit_error_is_returned_and_key_is_redacted(self) -> None:
        body = {"message": f"Too many requests for {API_KEY}"}
        with patch("httpx.Client.request", return_value=_response(429, json_body=body)):
            data = _make(OlostepSearchComponent, query="langflow").search()

        error = data[0].data["error"]
        assert "rate limit exceeded (429)" in error
        assert API_KEY not in error

    def test_key_cut_at_the_detail_limit_is_still_redacted(self) -> None:
        body = {"detail": "x" * 290 + API_KEY}
        with patch("httpx.Client.request", return_value=_response(500, json_body=body)):
            data = _make(OlostepSearchComponent, query="langflow").search()

        assert API_KEY[:10] not in data[0].data["error"]

    def test_invalid_key_402_is_explained(self) -> None:
        body = {"invalid_api_key": True, "message": "Your API key is invalid."}
        with patch("httpx.Client.request", return_value=_response(402, json_body=body)):
            data = _make(OlostepSearchComponent, query="langflow").search()

        error = data[0].data["error"]
        assert error.startswith("Olostep rejected the request: invalid API key or no credits left (402)")

    def test_nested_error_message_is_used(self) -> None:
        body = {"error": {"type": "malformed_request", "message": "query is required"}}
        with patch("httpx.Client.request", return_value=_response(400, json_body=body)):
            data = _make(OlostepSearchComponent, query="langflow").search()

        assert data[0].data["error"] == "Olostep API error (400): query is required"

    def test_non_json_response_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(text="<html>bad gateway</html>")):
            data = _make(OlostepSearchComponent, query="langflow").search()

        assert "not JSON" in data[0].data["error"]

    def test_timeout_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ReadTimeout("slow")):
            data = _make(OlostepSearchComponent, query="langflow", timeout=2.5).search()

        assert data[0].data["error"] == "Olostep request timed out after 2.5 seconds."

    def test_dataframe_output_has_one_row_per_result(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"result": {"links": SEARCH_LINKS}})):
            frame = _make(OlostepSearchComponent, query="langflow").search_dataframe()

        assert len(frame) == len(SEARCH_LINKS)
        assert list(frame["url"]) == [item["url"] for item in SEARCH_LINKS]


@pytest.mark.unit
class TestOlostepScrape:
    def test_scrape_returns_markdown(self) -> None:
        body = {
            "id": "scrape_1",
            "url": "https://www.langflow.org/",
            "result": {"markdown_content": "# Langflow", "page_metadata": {"title": "Langflow"}},
        }
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            page = _make(OlostepScrapeComponent, url="https://www.langflow.org/").scrape_page()

        method, url = request.call_args.args
        assert (method, url) == ("POST", f"{API_BASE_URL}/v1/scrapes")
        assert request.call_args.kwargs["json"] == {
            "url_to_scrape": "https://www.langflow.org/",
            "formats": ["markdown"],
        }
        assert page.text == "# Langflow"
        assert page.data["page_metadata"] == {"title": "Langflow"}

    def test_country_and_wait_are_sent(self) -> None:
        component = _make(OlostepScrapeComponent, url="https://example.com", country=" gb ", wait_before_scraping=2000)
        with patch("httpx.Client.request", return_value=_response(json_body={"result": {}})) as request:
            component.scrape_page()

        assert request.call_args.kwargs["json"] == {
            "url_to_scrape": "https://example.com",
            "formats": ["markdown"],
            "country": "GB",
            "wait_before_scraping": 2000,
        }

    @pytest.mark.parametrize(
        "url", ["", "example.com", "file:///etc/passwd", "ftp://example.com/x", "https://[example"]
    )
    def test_rejects_non_http_urls_without_a_request(self, url: str) -> None:
        with patch("httpx.Client.request") as request:
            page = _make(OlostepScrapeComponent, url=url).scrape_page()

        request.assert_not_called()
        assert "absolute http(s) URL" in page.data["error"]

    def test_unreachable_api_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ConnectError("connection refused")):
            page = _make(OlostepScrapeComponent, url="https://example.com").scrape_page()

        assert page.data["error"].startswith("Could not reach the Olostep API: ConnectError")


@pytest.mark.unit
class TestOlostepAnswer:
    def test_plain_answer_is_unwrapped(self) -> None:
        body = {
            "id": "answer_1",
            "result": {"json_content": json.dumps({"result": "Canberra"}), "sources": ["https://example.com/a"]},
        }
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            answer = _make(OlostepAnswerComponent, task="What is the capital of Australia?").get_answer()

        assert request.call_args.args[1] == f"{API_BASE_URL}/v1/answers"
        assert request.call_args.kwargs["json"] == {"task": "What is the capital of Australia?"}
        assert answer.text == "Canberra"
        assert answer.data["sources"] == ["https://example.com/a"]

    def test_output_fields_are_sent_as_an_object(self) -> None:
        fields = {"ceo": "", "founded": ""}
        body = {"result": {"json_content": json.dumps({"ceo": "Jane Doe", "founded": "2019"}), "sources": []}}
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            answer = _make(OlostepAnswerComponent, task="Acme facts", json_format=json.dumps(fields)).get_answer()

        assert request.call_args.kwargs["json"]["json_format"] == fields
        assert answer.data["answer"] == {"ceo": "Jane Doe", "founded": "2019"}
        assert json.loads(answer.text) == {"ceo": "Jane Doe", "founded": "2019"}

    def test_output_fields_can_be_a_description(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"result": {}})) as request:
            _make(OlostepAnswerComponent, task="Acme facts", json_format="the CEO and founding year").get_answer()

        assert request.call_args.kwargs["json"]["json_format"] == "the CEO and founding year"

    def test_empty_answer_says_so(self) -> None:
        body = {"result": {"json_content": json.dumps({"result": ""}), "sources": []}}
        with patch("httpx.Client.request", return_value=_response(json_body=body)):
            answer = _make(OlostepAnswerComponent, task="Something unknowable").get_answer()

        assert answer.text == "Olostep found no answer to this question on the web."

    def test_empty_question_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            answer = _make(OlostepAnswerComponent, task=" ").get_answer()

        request.assert_not_called()
        assert answer.data["error"] == "Enter a question."


@pytest.mark.unit
class TestOlostepMap:
    def test_map_returns_one_row_per_url(self) -> None:
        body = {"id": "map_1", "urls": ["https://example.com/", "https://example.com/about"]}
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            data = _make(OlostepMapComponent, url="https://example.com", include_urls="/blog/**", top_n=5).map_site()

        assert request.call_args.args[1] == f"{API_BASE_URL}/v1/maps"
        assert request.call_args.kwargs["json"] == {
            "url": "https://example.com",
            "top_n": 5,
            "include_urls": ["/blog/**"],
        }
        assert [item.text for item in data] == body["urls"]

    def test_cursor_pages_are_followed(self) -> None:
        responses = [
            _response(json_body={"urls": ["https://example.com/1"], "cursor": "next"}),
            _response(json_body={"urls": ["https://example.com/2"], "cursor": None}),
        ]
        with patch("httpx.Client.request", side_effect=responses) as request:
            data = _make(OlostepMapComponent, url="https://example.com").map_site()

        assert request.call_count == 2
        assert request.call_args.kwargs["json"]["cursor"] == "next"
        assert [item.text for item in data] == ["https://example.com/1", "https://example.com/2"]

    @pytest.mark.parametrize("has_more_results", [False, True])
    def test_map_request_limit_reports_incomplete_results(self, *, has_more_results: bool) -> None:
        response_count = MAX_CURSOR_PAGES + int(has_more_results)
        responses = [
            _response(
                json_body={
                    "urls": [f"https://example.com/{index}"],
                    "cursor": str(index + 1) if index + 1 < response_count else None,
                }
            )
            for index in range(response_count)
        ]
        component = _make(OlostepMapComponent, url="https://example.com")
        with patch("httpx.Client.request", side_effect=responses) as request:
            data = component.map_site()

        assert request.call_count == MAX_CURSOR_PAGES
        if has_more_results:
            assert len(data) == 1
            assert "incomplete" in data[0].data["error"].lower()
            assert component.status == data[0].data["error"]
        else:
            assert [item.data["url"] for item in data] == [
                f"https://example.com/{index}" for index in range(response_count)
            ]
            assert component.status == f"Found {response_count} URLs."

    def test_rejects_non_http_url_without_a_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _make(OlostepMapComponent, url="example.com").map_site()

        request.assert_not_called()
        assert "absolute http(s) URL" in data[0].data["error"]


@pytest.mark.unit
class TestOlostepCrawl:
    @pytest.mark.parametrize("has_more_results", [False, True])
    def test_crawl_request_limit_reports_incomplete_results(self, *, has_more_results: bool) -> None:
        response_count = _MAX_PAGE_REQUESTS + int(has_more_results)
        responses = [_response(json_body={"id": "crawl_limit", "status": "completed"})]
        responses.extend(
            _response(
                json_body={
                    "pages": [{"url": f"https://example.com/{index}", "markdown_content": f"Page {index}"}],
                    "cursor": index + 1 if index + 1 < response_count else None,
                }
            )
            for index in range(response_count)
        )
        component = _make(OlostepCrawlComponent, start_url="https://example.com", max_pages=response_count)
        with patch("httpx.Client.request", side_effect=responses) as request:
            data = component.crawl()

        assert request.call_count == _MAX_PAGE_REQUESTS + 1
        if has_more_results:
            assert len(data) == 1
            assert "incomplete" in data[0].data["error"].lower()
            assert component.status == data[0].data["error"]
        else:
            assert [item.data["url"] for item in data] == [
                f"https://example.com/{index}" for index in range(response_count)
            ]
            assert component.status == f"Crawled {response_count} pages."

    def test_crawl_waits_then_returns_pages(self) -> None:
        responses = [
            _response(json_body={"id": "crawl_1", "status": "in_progress"}),
            _response(json_body={"id": "crawl_1", "status": "completed"}),
            _response(
                json_body={
                    "pages": [
                        {"url": "https://example.com/", "markdown_content": "# Home"},
                        {"url": "https://example.com/a", "markdown_content": "# A"},
                    ]
                }
            ),
        ]
        with (
            patch("httpx.Client.request", side_effect=responses) as request,
            patch("lfx_bundles.olostep.olostep_crawl.time.sleep") as sleep,
        ):
            component = _make(OlostepCrawlComponent, start_url="https://example.com", max_pages=2, wait_seconds=60)
            data = component.crawl()

        create, status, pages = request.call_args_list
        assert create.args == ("POST", f"{API_BASE_URL}/v1/crawls")
        assert create.kwargs["json"] == {"start_url": "https://example.com", "max_pages": 2, "timeout": 40}
        assert status.args == ("GET", f"{API_BASE_URL}/v1/crawls/crawl_1")
        assert pages.args == ("GET", f"{API_BASE_URL}/v1/crawls/crawl_1/pages")
        assert pages.kwargs["params"]["formats"] == "markdown"
        sleep.assert_called_once()
        assert [item.text for item in data] == ["# Home", "# A"]
        assert data[0].data["crawl_id"] == "crawl_1"
        assert component.status == "Crawled 2 pages."

    def test_crawl_returns_pages_done_when_the_wait_runs_out(self) -> None:
        responses = [
            _response(json_body={"id": "crawl_2", "status": "in_progress"}),
            _response(json_body={"pages": [{"url": "https://example.com/", "markdown_content": "# Home"}]}),
        ]
        # The first deadline check already sees the wait as over.
        clock = iter([0.0, 1000.0])
        with (
            patch("httpx.Client.request", side_effect=responses),
            patch("lfx_bundles.olostep.olostep_crawl.time.monotonic", side_effect=lambda: next(clock)),
        ):
            component = _make(OlostepCrawlComponent, start_url="https://example.com", wait_seconds=30)
            data = component.crawl()

        assert len(data) == 1
        assert "still running" in component.status

    def test_include_exclude_and_depth_are_sent(self) -> None:
        responses = [
            _response(json_body={"id": "crawl_3", "status": "completed"}),
            _response(json_body={"pages": []}),
        ]
        with patch("httpx.Client.request", side_effect=responses) as request:
            _make(
                OlostepCrawlComponent,
                start_url="https://example.com",
                include_urls="/docs/**",
                exclude_urls="/blog/**, /careers/**",
                max_depth=2,
            ).crawl()

        sent = request.call_args_list[0].kwargs["json"]
        assert sent["include_urls"] == ["/docs/**"]
        assert sent["exclude_urls"] == ["/blog/**", "/careers/**"]
        assert sent["max_depth"] == 2

    def test_create_error_is_returned(self) -> None:
        with patch("httpx.Client.request", return_value=_response(401, json_body={"message": "Invalid API key"})):
            data = _make(OlostepCrawlComponent, start_url="https://example.com").crawl()

        assert data[0].data["error"] == "Olostep rejected the API key (401): Invalid API key"
