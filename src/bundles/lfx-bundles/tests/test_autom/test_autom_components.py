"""Unit tests for the Autom components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the
real endpoint, headers, parameters and error handling of the client.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.autom.autom_common import API_BASE_URL
from lfx_bundles.autom.autom_google_news import AutomGoogleNewsComponent
from lfx_bundles.autom.autom_google_search import AutomGoogleSearchComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-autom-api-key-placeholder"  # pragma: allowlist secret

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
NEWS_ROWS = [
    {
        "position": 1,
        "title": "Agents ship",
        "link": "https://news.example.com/agents",
        "source": "Example News",
        "snippet": "Teams put agents in production.",
        "date": "2 hours ago",
    }
]
COMPONENTS = [AutomGoogleSearchComponent, AutomGoogleNewsComponent]


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _search(**values) -> AutomGoogleSearchComponent:
    component = AutomGoogleSearchComponent()
    component.set(**{"api_key": API_KEY, "query": "langflow agents", **values})
    return component


def _news(**values) -> AutomGoogleNewsComponent:
    component = AutomGoogleNewsComponent()
    component.set(**{"api_key": API_KEY, "query": "ai agents", **values})
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
    assert component.icon == "Autom"
    assert "docs.autom.dev" in component.documentation
    api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
    assert api_key.required is True
    query = next(inp for inp in component_class.inputs if inp.name == "query")
    assert query.tool_mode is True


@pytest.mark.unit
class TestAutomGoogleSearch:
    def test_search_sends_the_key_and_maps_rows(self) -> None:
        with patch(
            "httpx.Client.request", return_value=_response(json_body={"organic_results": SEARCH_ROWS})
        ) as request:
            data = _search(api_key=f"  {API_KEY}  ").search()

        method, url = request.call_args.args
        assert method == "GET"
        assert url == f"{API_BASE_URL}/v1/google/search"
        assert request.call_args.kwargs["headers"]["x-api-key"] == API_KEY
        assert request.call_args.kwargs["params"] == {"query": "langflow agents"}
        assert [item.text for item in data] == [SEARCH_ROWS[0]["snippet"], "Only a title"]
        assert data[0].data["link"] == "https://www.langflow.org/"

    def test_optional_parameters_are_sent(self) -> None:
        component = _search(country=" US ", language="fr", location=" Paris, France ", time_range="Past week")
        with patch("httpx.Client.request", return_value=_response(json_body={"organic_results": []})) as request:
            component.search()

        assert request.call_args.kwargs["params"] == {
            "query": "langflow agents",
            "gl": "us",
            "hl": "fr",
            "location": "Paris, France",
            "tbs": "qdr:w",
        }

    @pytest.mark.parametrize(("max_results", "expected"), [(1, 1), (0, 1), (5, 5), (99, 10)])
    def test_max_results_trims_client_side(self, max_results: Any, expected: int) -> None:
        rows = [{"title": f"T{i}", "link": f"https://example.com/{i}", "snippet": "s"} for i in range(12)]
        with patch("httpx.Client.request", return_value=_response(json_body={"organic_results": rows})):
            data = _search(max_results=max_results).search()

        assert len(data) == expected

    def test_missing_organic_results_is_an_empty_search(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"search_parameters": {}})):
            assert _search().search() == []

    def test_non_list_organic_results_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"organic_results": "oops"})):
            data = _search().search()

        assert "not a list" in data[0].data["error"]

    def test_empty_query_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _search(query="   ").search()

        request.assert_not_called()
        assert data[0].data["error"] == "Enter a search query."

    def test_missing_key_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _search(api_key="  ").search()

        request.assert_not_called()
        assert data[0].data["error"] == "Enter an Autom API key."

    def test_invalid_key_error_is_returned(self) -> None:
        with patch("httpx.Client.request", return_value=_response(401, json_body={"error": "Invalid API key"})):
            data = _search().search()

        assert data[0].data["error"] == "Autom rejected the API key (401): Invalid API key"

    def test_rate_limit_answered_as_401_is_labelled_as_a_rate_limit(self) -> None:
        body = {"error": f"Rate limit exceeded for {API_KEY}"}
        with patch("httpx.Client.request", return_value=_response(401, json_body=body)):
            data = _search().search()

        error = data[0].data["error"]
        assert error.startswith("Autom rate limit exceeded (401)")
        assert API_KEY not in error

    def test_key_cut_at_the_detail_limit_is_still_redacted(self) -> None:
        body = {"message": "x" * 290 + API_KEY}
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

        assert data[0].data["error"] == "Autom request timed out after 2.5 seconds."

    def test_unreachable_api_is_an_error_without_the_key(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ConnectError(f"refused {API_KEY}")):
            data = _search().search()

        error = data[0].data["error"]
        assert error.startswith("Could not reach the Autom API: ConnectError")
        assert API_KEY not in error

    def test_dataframe_output_has_one_row_per_result(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"organic_results": SEARCH_ROWS})):
            frame = _search().search_dataframe()

        assert len(frame) == 2
        assert list(frame["link"]) == ["https://www.langflow.org/", "https://example.com/"]


@pytest.mark.unit
class TestAutomGoogleNews:
    def test_news_uses_the_news_endpoint(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"organic_results": NEWS_ROWS})) as request:
            data = _news(country="GB", language="en").news()

        assert request.call_args.args[1] == f"{API_BASE_URL}/v1/google/news"
        assert request.call_args.kwargs["params"] == {"query": "ai agents", "gl": "gb", "hl": "en"}
        assert data[0].text == "Teams put agents in production."
        assert data[0].data["source"] == "Example News"
        assert data[0].data["date"] == "2 hours ago"

    def test_news_error_is_returned(self) -> None:
        with patch("httpx.Client.request", return_value=_response(402, json_body={"message": "No credits left"})):
            data = _news().news()

        assert data[0].data["error"] == "Autom account is out of credits (402): No credits left"

    def test_news_dataframe(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"organic_results": NEWS_ROWS})):
            frame = _news().news_dataframe()

        assert list(frame["source"]) == ["Example News"]
