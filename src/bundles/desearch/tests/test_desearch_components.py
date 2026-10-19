"""Unit tests for the Desearch extension bundle (``lfx-desearch``).

The components call the Desearch REST API with ``httpx``; the tests patch
``httpx.request`` at the shared client module to return real ``httpx.Response``
objects, so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_desearch import DesearchAISearchComponent, DesearchWebSearchComponent, DesearchXSearchComponent

REQUEST_PATCH_TARGET = "lfx_desearch.components.desearch._client.httpx.request"
TEST_KEY = "test-key"  # pragma: allowlist secret

WEB_PAYLOAD = {
    "data": [
        {"title": "Result one", "link": "https://example.com/one", "snippet": "First snippet."},
        {"title": "Result two", "link": "https://example.com/two", "snippet": "Second snippet."},
        "not-a-dict",
    ],
    "cost_usd": 0.0025,
}

AI_PAYLOAD = {
    "search": [
        {"title": "Langflow", "link": "https://example.com/langflow"},
        {"title": "Langflow duplicate", "link": "https://example.com/langflow"},
    ],
    "tweets": [{"text": "A post", "url": "https://x.com/a/status/1"}],
    "completion": "Langflow is a visual builder.",
}

X_PAYLOAD = [
    {
        "id": "1",
        "url": "https://x.com/a/status/1",
        "text": "Hello from X",
        "created_at": "2026-10-17T00:00:00Z",
        "user": {"username": "a"},
        "like_count": 3,
        "retweet_count": 1,
        "reply_count": 0,
    },
    "not-a-dict",
]


def _response(status_code: int = 200, method: str = "GET", **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request(method, "https://api.desearch.ai/x"), **kwargs)


def _mock(payload: object = None, status_code: int = 200, **kwargs) -> MagicMock:
    if payload is not None:
        kwargs["json"] = payload
    return MagicMock(return_value=_response(status_code, **kwargs))


@pytest.fixture
def web() -> DesearchWebSearchComponent:
    c = DesearchWebSearchComponent()
    c.input_value = "langflow"
    c.desearch_api_key = TEST_KEY
    c.offset = 0
    return c


@pytest.fixture
def ai() -> DesearchAISearchComponent:
    c = DesearchAISearchComponent()
    c.input_value = "What is Langflow?"
    c.desearch_api_key = TEST_KEY
    c.sources = ["web", "twitter"]
    c.date_filter = "ANY_TIME"
    return c


@pytest.fixture
def x() -> DesearchXSearchComponent:
    c = DesearchXSearchComponent()
    c.input_value = "langflow"
    c.desearch_api_key = TEST_KEY
    c.count = 10
    c.sort = "Top"
    c.user = ""
    c.lang = ""
    c.start_date = ""
    c.end_date = ""
    return c


def test_class_names_are_stable():
    """Class names must stay stable for saved flows."""
    assert DesearchWebSearchComponent.__name__ == "DesearchWebSearchComponent"
    assert DesearchAISearchComponent.__name__ == "DesearchAISearchComponent"
    assert DesearchXSearchComponent.__name__ == "DesearchXSearchComponent"


# --- Web search -----------------------------------------------------------


def test_web_sends_raw_key_and_query(web):
    mock = _mock(WEB_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        web.fetch_content()
    method, url = mock.call_args.args
    assert method == "GET"
    assert url == "https://api.desearch.ai/web"
    assert mock.call_args.kwargs["headers"]["Authorization"] == TEST_KEY
    assert mock.call_args.kwargs["params"] == {"query": "langflow"}


def test_web_sends_offset_when_set(web):
    web.offset = 20
    mock = _mock(WEB_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        web.fetch_content()
    assert mock.call_args.kwargs["params"] == {"query": "langflow", "start": 20}


def test_web_maps_results_and_skips_malformed(web):
    with patch(REQUEST_PATCH_TARGET, _mock(WEB_PAYLOAD)):
        results = web.fetch_content()
    assert [r.data["title"] for r in results] == ["Result one", "Result two"]
    assert results[0].data["link"] == "https://example.com/one"
    assert results[0].data["snippet"] == "First snippet."
    assert results[0].text == "First snippet."


def test_web_missing_key_returns_error_without_request(web):
    web.desearch_api_key = ""
    mock = _mock(WEB_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        results = web.fetch_content()
    mock.assert_not_called()
    assert "Desearch API key is required" in results[0].data["error"]


def test_web_surfaces_api_error_detail(web):
    with patch(REQUEST_PATCH_TARGET, _mock({"detail": "Forbidden"}, status_code=403)):
        results = web.fetch_content()
    assert results[0].data["error"] == "Desearch API error 403: Forbidden"


def test_web_http_error_without_json_body(web):
    with patch(REQUEST_PATCH_TARGET, _mock(status_code=502, text="bad gateway")):
        results = web.fetch_content()
    assert results[0].data["error"].startswith("Desearch API error 502")


def test_web_network_error(web):
    with patch(REQUEST_PATCH_TARGET, MagicMock(side_effect=httpx.ConnectError("boom"))):
        results = web.fetch_content()
    assert results[0].data["error"] == "boom"


def test_web_rejects_non_object_payload(web):
    with patch(REQUEST_PATCH_TARGET, _mock(["unexpected"])):
        results = web.fetch_content()
    assert "unexpected response" in results[0].data["error"]


def test_web_dataframe_shape(web):
    with patch(REQUEST_PATCH_TARGET, _mock(WEB_PAYLOAD)):
        df = web.desearch_web_search()
    assert list(df["title"]) == ["Result one", "Result two"]


# --- AI search ------------------------------------------------------------


def test_ai_sends_prompt_sources_and_no_streaming(ai):
    mock = _mock(AI_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        ai.desearch_ai_search()
    method, url = mock.call_args.args
    assert method == "POST"
    assert url == "https://api.desearch.ai/desearch/ai/search"
    assert mock.call_args.kwargs["headers"]["Authorization"] == TEST_KEY
    assert mock.call_args.kwargs["json"] == {
        "prompt": "What is Langflow?",
        "tools": ["web", "twitter"],
        "streaming": False,
    }


def test_ai_date_filter_and_unknown_sources(ai):
    ai.date_filter = "PAST_WEEK"
    ai.sources = ["youtube"]
    mock = _mock(AI_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        ai.desearch_ai_search()
    body = mock.call_args.kwargs["json"]
    assert body["date_filter"] == "PAST_WEEK"
    assert body["tools"] == ["web", "twitter"]


def test_ai_answer_lists_unique_sources(ai):
    with patch(REQUEST_PATCH_TARGET, _mock(AI_PAYLOAD)):
        message = ai.desearch_ai_search()
    assert message.text.startswith("Langflow is a visual builder.")
    assert message.text.count("https://example.com/langflow") == 1
    assert "https://x.com/a/status/1" in message.text


def test_ai_source_titles_are_short_single_lines(ai):
    payload = {
        "tweets": [{"text": "First line of a post\nsecond line " + "x" * 200, "url": "https://x.com/a/status/2"}]
    }
    with patch(REQUEST_PATCH_TARGET, _mock(payload)):
        df = ai.desearch_ai_sources()
    assert list(df["title"]) == ["First line of a post"]
    long_payload = {"tweets": [{"text": "y" * 300, "url": "https://x.com/a/status/3"}]}
    ai.input_value = "another prompt"
    with patch(REQUEST_PATCH_TARGET, _mock(long_payload)):
        df = ai.desearch_ai_sources()
    assert len(df["title"][0]) == 100
    assert df["title"][0].endswith("...")


def test_ai_outputs_share_one_request(ai):
    mock = _mock(AI_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        ai.desearch_ai_search()
        df = ai.desearch_ai_sources()
    assert mock.call_count == 1
    assert list(df["link"]) == ["https://example.com/langflow", "https://x.com/a/status/1"]


def test_ai_new_prompt_runs_new_request(ai):
    mock = _mock(AI_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        ai.desearch_ai_search()
        ai.input_value = "Another question"
        ai.desearch_ai_search()
    assert mock.call_count == 2


def test_ai_error_is_not_cached(ai):
    with patch(REQUEST_PATCH_TARGET, _mock({"detail": "Unauthorized"}, status_code=401, method="POST")):
        message = ai.desearch_ai_search()
    assert message.text == "Desearch API error 401: Unauthorized"
    mock = _mock(AI_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        message = ai.desearch_ai_search()
    assert mock.call_count == 1
    assert message.text.startswith("Langflow is a visual builder.")


def test_ai_changed_or_cleared_key_skips_cache(ai):
    mock = _mock(AI_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        ai.desearch_ai_search()
        ai.desearch_api_key = "other-key"  # pragma: allowlist secret
        ai.desearch_ai_search()
        ai.desearch_api_key = ""
        message = ai.desearch_ai_search()
    assert mock.call_count == 2
    assert "Desearch API key is required" in message.text


def test_ai_sources_are_supported_tools_only():
    from lfx_desearch.components.desearch.desearch_ai_search import SOURCES

    assert SOURCES == ["web", "twitter"]


def test_ai_missing_key(ai):
    ai.desearch_api_key = ""
    mock = _mock(AI_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        df = ai.desearch_ai_sources()
    mock.assert_not_called()
    assert "Desearch API key is required" in df["error"][0]


def test_ai_validation_error_detail(ai):
    payload = {"detail": [{"loc": ["body", "prompt"], "msg": "Field required"}]}
    with patch(REQUEST_PATCH_TARGET, _mock(payload, status_code=422, method="POST")):
        message = ai.desearch_ai_search()
    assert message.text == "Desearch API error 422: Field required"


# --- X search -------------------------------------------------------------


def test_x_sends_params(x):
    x.user = "@desearch"
    x.lang = "en"
    x.sort = "Latest"
    mock = _mock(X_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        x.fetch_content()
    method, url = mock.call_args.args
    assert (method, url) == ("GET", "https://api.desearch.ai/twitter")
    assert mock.call_args.kwargs["headers"]["Authorization"] == TEST_KEY
    assert mock.call_args.kwargs["params"] == {
        "query": "langflow",
        "count": 10,
        "sort": "Latest",
        "user": "desearch",
        "lang": "en",
    }


@pytest.mark.parametrize(("requested", "expected"), [(0, 1), (500, 100), (None, 10)])
def test_x_count_is_clamped(x, requested, expected):
    x.count = requested
    mock = _mock(X_PAYLOAD)
    with patch(REQUEST_PATCH_TARGET, mock):
        x.fetch_content()
    assert mock.call_args.kwargs["params"]["count"] == expected


def test_x_maps_posts(x):
    with patch(REQUEST_PATCH_TARGET, _mock(X_PAYLOAD)):
        results = x.fetch_content()
    assert len(results) == 1
    assert results[0].data["username"] == "a"
    assert results[0].data["url"] == "https://x.com/a/status/1"
    assert results[0].text == "Hello from X"


def test_x_rejects_non_list_payload(x):
    with patch(REQUEST_PATCH_TARGET, _mock({"data": []})):
        results = x.fetch_content()
    assert "expected a JSON list" in results[0].data["error"]


def test_x_dataframe_shape(x):
    with patch(REQUEST_PATCH_TARGET, _mock(X_PAYLOAD)):
        df = x.desearch_x_search()
    assert list(df["username"]) == ["a"]


# --- Tool mode ------------------------------------------------------------


@pytest.mark.parametrize(
    ("component_cls", "tool_name", "payload"),
    [
        (DesearchWebSearchComponent, "desearch_web_search", WEB_PAYLOAD),
        (DesearchAISearchComponent, "desearch_ai_search", AI_PAYLOAD),
        (DesearchXSearchComponent, "desearch_x_search", X_PAYLOAD),
    ],
)
def test_tool_mode_exposes_one_desearch_specific_tool(component_cls, tool_name, payload):
    """The agent-facing tool names must not collide with other search components."""
    # Tools read inputs the way a graph sets them (constructor kwargs), not
    # attributes assigned after construction, so build the component directly.
    component = component_cls(desearch_api_key=TEST_KEY)
    tools = asyncio.run(component.to_toolkit())
    assert [tool.name for tool in tools] == [tool_name]
    mock = _mock(payload)
    with patch(REQUEST_PATCH_TARGET, mock):
        output = asyncio.run(tools[0].ainvoke({"input_value": "langflow"}))
    assert mock.call_count == 1
    assert mock.call_args.kwargs["headers"]["Authorization"] == TEST_KEY
    assert "error" not in str(output).lower()


# --- Palette template -----------------------------------------------------


@pytest.mark.parametrize(
    "component_cls", [DesearchWebSearchComponent, DesearchAISearchComponent, DesearchXSearchComponent]
)
def test_palette_template_builds_from_component_source(component_cls):
    """Langflow rebuilds each class from its source code, so helper imports must be absolute."""
    from lfx.custom.utils import create_component_template

    template, _ = create_component_template(component_extractor=component_cls(), module_name=component_cls.__module__)
    assert template["display_name"] == component_cls.display_name
    assert "desearch_api_key" in template["template"]
