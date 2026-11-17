"""Unit tests for the cloro components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.post``, so the tests exercise the real
URL, headers, payloads and error handling of the client. The response bodies
follow the shape of real cloro responses, cut down to a few items.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.cloro.cloro_ai_mode import CloroAIModeComponent
from lfx_bundles.cloro.cloro_bing_ai_mode import CloroBingAIModeComponent
from lfx_bundles.cloro.cloro_chatgpt import CloroChatGPTComponent
from lfx_bundles.cloro.cloro_common import API_BASE_URL
from lfx_bundles.cloro.cloro_gemini import CloroGeminiComponent
from lfx_bundles.cloro.cloro_google_search import CloroGoogleSearchComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-cloro-api-key-placeholder"  # pragma: allowlist secret

ALL_COMPONENTS = [
    CloroGoogleSearchComponent,
    CloroChatGPTComponent,
    CloroAIModeComponent,
    CloroBingAIModeComponent,
    CloroGeminiComponent,
]
ANSWER_COMPONENTS = [
    (CloroChatGPTComponent, "chatgpt"),
    (CloroAIModeComponent, "aimode"),
    (CloroBingAIModeComponent, "bing_aimode"),
    (CloroGeminiComponent, "gemini"),
]
# The endpoint path of each engine, where it differs from the engine name.
ENDPOINT_PATHS = {"bing_aimode": "bing/aimode"}

GOOGLE_RESULT = {
    "organicResults": [
        {
            "position": 1,
            "title": "The 12 best rank tracker tools",
            "link": "https://zapier.com/blog/best-rank-tracker/",
            "displayedLink": "https://zapier.com > App picks",
            "snippet": "Best overall rank tracker.",
            "page": 1,
        },
        {"position": 2, "title": "No link", "link": "", "snippet": "Skipped."},
        {
            "position": 3,
            "title": "Redirect only",
            "link": "https://www.google.com/goto?url=CAESZwHEIkXX",
            "snippet": "Skipped.",
        },
        {"position": 4, "title": "Rank tracking", "link": "https://seranking.com/position-tracking.html"},
    ],
    "peopleAlsoAsk": [],
    "relatedSearches": [],
    "aioverview": {
        "text": "The best rank tracker tools cater to different needs.",
        "sources": [
            {
                "label": "The 12 best rank tracker tools | Zapier",
                "url": "https://zapier.com/blog/best-rank-tracker/",
                "position": 1,
                "redirectLink": "https://www.google.com/goto?url=CAESZw",
            },
            {"label": "Redirect only", "url": "https://www.google.com/goto?url=CAESkA", "position": 2},
        ],
        "citationPills": [],
    },
}

ANSWER_RESULT = {
    "text": "Here are my top picks.",
    "markdown": "## Top picks\n\n1. SE Ranking",
    "sources": [
        {"position": 1, "label": "SE Ranking FAQ", "url": "https://seranking.com/faq.html", "footnote": False},
        {"position": 2, "label": "", "url": "https://www.seo.com/tools/rank-tracking/", "footnote": True},
    ],
    "citationPills": [],
    "model": None,
}


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("POST", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _ok(result: dict[str, Any]) -> httpx.Response:
    return _response(json_body={"success": True, "result": result})


def _error(status_code: int, code: str, message: str) -> httpx.Response:
    return _response(status_code, json_body={"success": False, "error": {"code": code, "message": message}})


def _answer_component(component_class: type[Component], **values) -> Component:
    component = component_class()
    component.set(**{"api_key": API_KEY, "prompt": "best rank tracker", **values})
    return component


def _search(**values) -> CloroGoogleSearchComponent:
    component = CloroGoogleSearchComponent()
    component.set(**{"api_key": API_KEY, "query": "best rank tracker", **values})
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
    assert component.icon == "Cloro"
    assert component.documentation.startswith("https://cloro.dev/docs")
    api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
    assert api_key.required is True


@pytest.mark.unit
class TestCloroGoogleSearch:
    def test_request_shape(self) -> None:
        with patch("httpx.Client.post", return_value=_ok(GOOGLE_RESULT)) as post:
            _search(api_key=f"  {API_KEY}  ", country=" de ").search()

        assert post.call_args.args == (f"{API_BASE_URL}/v1/monitor/google",)
        assert post.call_args.kwargs["headers"] == {"Authorization": f"Bearer {API_KEY}"}
        assert post.call_args.kwargs["json"] == {
            "query": "best rank tracker",
            "country": "DE",
            "include": {"aioverview": True},
        }

    def test_ai_overview_can_be_turned_off(self) -> None:
        with patch("httpx.Client.post", return_value=_ok(GOOGLE_RESULT)) as post:
            _search(include_ai_overview=False).search()

        assert "include" not in post.call_args.kwargs["json"]

    def test_ai_overview_is_the_first_row_with_its_sources(self) -> None:
        with patch("httpx.Client.post", return_value=_ok(GOOGLE_RESULT)):
            rows = _search().search()

        overview = rows[0].data
        assert overview["type"] == "ai_overview"
        assert rows[0].text == GOOGLE_RESULT["aioverview"]["text"]
        assert overview["sources"] == [
            {"label": "The 12 best rank tracker tools | Zapier", "url": "https://zapier.com/blog/best-rank-tracker/"}
        ]

    def test_results_without_a_usable_link_are_skipped(self) -> None:
        with patch("httpx.Client.post", return_value=_ok(GOOGLE_RESULT)):
            rows = _search().search()

        organic = [row.data for row in rows if row.data["type"] == "organic"]
        assert [row["position"] for row in organic] == [1, 4]
        assert organic[1]["link"] == "https://seranking.com/position-tracking.html"
        # A result with no snippet falls back to its title as text.
        assert rows[-1].text == "Rank tracking"

    def test_no_ai_overview_in_response(self) -> None:
        result = {key: value for key, value in GOOGLE_RESULT.items() if key != "aioverview"}
        with patch("httpx.Client.post", return_value=_ok(result)):
            rows = _search().search()

        assert [row.data["type"] for row in rows] == ["organic", "organic"]

    def test_dataframe_output_has_one_row_per_item(self) -> None:
        with patch("httpx.Client.post", return_value=_ok(GOOGLE_RESULT)):
            frame = _search().search_dataframe()

        assert list(frame["type"]) == ["ai_overview", "organic", "organic"]
        assert list(frame["link"])[1:] == [
            "https://zapier.com/blog/best-rank-tracker/",
            "https://seranking.com/position-tracking.html",
        ]

    def test_empty_query_makes_no_request(self) -> None:
        with patch("httpx.Client.post") as post:
            rows = _search(query="   ").search()

        post.assert_not_called()
        assert rows[0].data["error"] == "Enter a search query."

    def test_missing_key_makes_no_request(self) -> None:
        with patch("httpx.Client.post") as post:
            rows = _search(api_key="").search()

        post.assert_not_called()
        assert rows[0].data["error"] == "Enter a cloro API key."

    def test_bad_key_error_is_returned(self) -> None:
        with patch("httpx.Client.post", return_value=_error(401, "INVALID_API_KEY_FORMAT", "Invalid API key format")):
            rows = _search().search()

        assert (
            rows[0].data["error"] == "cloro rejected the API key (401): INVALID_API_KEY_FORMAT: Invalid API key format"
        )

    def test_key_is_redacted_from_errors(self) -> None:
        with patch("httpx.Client.post", return_value=_error(500, "INTERNAL", f"Failed for {API_KEY}")):
            rows = _search().search()

        assert API_KEY not in rows[0].data["error"]
        assert "***" in rows[0].data["error"]

    def test_key_cut_at_the_detail_limit_is_still_redacted(self) -> None:
        # The key straddles the 300-character cap on the echoed detail.
        with patch("httpx.Client.post", return_value=_error(500, "INTERNAL", "x" * 280 + API_KEY)):
            rows = _search().search()

        assert API_KEY[:10] not in rows[0].data["error"]

    def test_non_json_response_is_an_error(self) -> None:
        with patch("httpx.Client.post", return_value=_response(text="<html>bad gateway</html>")):
            rows = _search().search()

        assert "not JSON" in rows[0].data["error"]

    def test_unexpected_shape_is_an_error(self) -> None:
        with patch("httpx.Client.post", return_value=_response(json_body={"success": True})):
            rows = _search().search()

        assert rows[0].data["error"] == "cloro API returned an unexpected response shape."

    def test_timeout_is_an_error(self) -> None:
        with patch("httpx.Client.post", side_effect=httpx.ReadTimeout("slow")):
            rows = _search(timeout=2.5).search()

        assert rows[0].data["error"] == "cloro request timed out after 2.5 seconds."

    def test_unreachable_api_is_an_error(self) -> None:
        with patch("httpx.Client.post", side_effect=httpx.ConnectError("connection refused")):
            rows = _search().search()

        assert rows[0].data["error"].startswith("Could not reach the cloro API: ConnectError")


@pytest.mark.unit
@pytest.mark.parametrize(("component_class", "engine"), ANSWER_COMPONENTS)
class TestCloroAnswers:
    def test_request_shape(self, component_class: type[Component], engine: str) -> None:
        with patch("httpx.Client.post", return_value=_ok(ANSWER_RESULT)) as post:
            _answer_component(component_class, country="gb").get_answer()

        assert post.call_args.args == (f"{API_BASE_URL}/v1/monitor/{ENDPOINT_PATHS.get(engine, engine)}",)
        assert post.call_args.kwargs["headers"] == {"Authorization": f"Bearer {API_KEY}"}
        assert post.call_args.kwargs["json"] == {
            "prompt": "best rank tracker",
            "country": "GB",
            "include": {"markdown": True},
        }

    def test_answer_and_every_source_are_returned(self, component_class: type[Component], engine: str) -> None:
        with patch("httpx.Client.post", return_value=_ok(ANSWER_RESULT)):
            answer = _answer_component(component_class).get_answer()

        assert answer.data["engine"] == engine
        assert answer.data["answer"] == ANSWER_RESULT["markdown"]
        # Every source counts, whatever its footnote flag says.
        assert [source["url"] for source in answer.data["sources"]] == [
            "https://seranking.com/faq.html",
            "https://www.seo.com/tools/rank-tracking/",
        ]
        assert answer.text == (
            "## Top picks\n\n1. SE Ranking\n\nSources:\n"
            "1. SE Ranking FAQ: https://seranking.com/faq.html\n"
            "2. https://www.seo.com/tools/rank-tracking/: https://www.seo.com/tools/rank-tracking/"
        )

    def test_plain_text_is_used_without_markdown(self, component_class: type[Component], engine: str) -> None:
        result = {"text": "Plain answer.", "sources": [], "citationPills": []}
        with patch("httpx.Client.post", return_value=_ok(result)):
            answer = _answer_component(component_class).get_answer()

        assert answer.text == "Plain answer."
        assert answer.data["sources"] == []
        assert answer.data["engine"] == engine


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [component for component, _ in ANSWER_COMPONENTS])
def test_answer_with_empty_prompt_makes_no_request(component_class: type[Component]) -> None:
    with patch("httpx.Client.post") as post:
        answer = _answer_component(component_class, prompt=" ").get_answer()

    post.assert_not_called()
    assert answer.data["error"] == "Enter a prompt."


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [component for component, _ in ANSWER_COMPONENTS])
def test_answer_out_of_credits_error_is_returned(component_class: type[Component]) -> None:
    response = _error(403, "INSUFFICIENT_CREDITS", "Not enough credits")
    with patch("httpx.Client.post", return_value=response):
        answer = _answer_component(component_class).get_answer()

    assert answer.data["error"] == "cloro refused the request (403): INSUFFICIENT_CREDITS: Not enough credits"


@pytest.mark.unit
def test_bing_ai_mode_answer_keeps_every_source() -> None:
    # Cut down from a real cloro Bing AI Mode response: no markdown, no model field.
    result = {
        "text": "The ASICS Gel Pulse 15, Brooks Glycerin 21, and Saucony Guide 19 are good picks.",
        "sources": [
            {
                "position": 1,
                "label": "Best Running Shoes Under $150 in 2026: 8 Picks Worth the Money",
                "url": "https://runninggearlab.com/best-running-shoes-under-150/",
                "description": "The best running shoes under $150 in 2026.",
            }
        ],
        "citationPills": [
            {
                "position": 1,
                "label": "Best Running Shoes Under $150 in 2026: 8 Picks Worth the Money",
                "url": "https://runninggearlab.com/best-running-shoes-under-150/",
                "domain": "runninggearlab.com",
                "citationPillId": 1,
            }
        ],
    }
    with patch("httpx.Client.post", return_value=_ok(result)):
        answer = _answer_component(CloroBingAIModeComponent).get_answer()

    assert answer.data["engine"] == "bing_aimode"
    assert answer.data["answer"] == result["text"]
    assert answer.data["sources"] == [
        {
            "label": "Best Running Shoes Under $150 in 2026: 8 Picks Worth the Money",
            "url": "https://runninggearlab.com/best-running-shoes-under-150/",
        }
    ]
    assert answer.data["model"] is None
    assert answer.text.endswith(
        "Sources:\n1. Best Running Shoes Under $150 in 2026: 8 Picks Worth the Money: "
        "https://runninggearlab.com/best-running-shoes-under-150/"
    )
