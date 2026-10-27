"""Unit tests for the Bowmark extension bundle (``lfx-bowmark``).

The components call the Bowmark API with ``httpx``; the tests patch ``httpx.get``
and ``httpx.post`` at the component modules to return real ``httpx.Response``
objects, so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_bowmark import BowmarkLibraryComponent, BowmarkRunComponent

GET_PATCH_TARGET = "lfx_bowmark.components.bowmark.bowmark_library.httpx.get"
POST_PATCH_TARGET = "lfx_bowmark.components.bowmark.bowmark_run.httpx.post"
LIBRARY_URL = "https://api.bowmark.ai/v1/library"
RUN_URL = "https://api.bowmark.ai/v1/run"

LIBRARY_TEXT = "# Provider: Hacker News  (call as `bowmark.providers.hackernews`)\n"
RUN_OK = {
    "ok": True,
    "status": "ok",
    "result": [{"title": "Story one", "points": 120}],
    "logs": ["fetched 1"],
    "error": None,
    "ms": 2100,
    "runId": "run-123",
}


def _response(method: str, url: str, status_code: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request(method, url), **kwargs)


@pytest.fixture
def library() -> BowmarkLibraryComponent:
    c = BowmarkLibraryComponent()
    c.query = "news.ycombinator.com"
    c.bowmark_api_key = "test-key"  # pragma: allowlist secret
    return c


@pytest.fixture
def run() -> BowmarkRunComponent:
    c = BowmarkRunComponent()
    c.script = "return 1"
    c.bowmark_api_key = "test-key"  # pragma: allowlist secret
    c.timeout = 60
    return c


def test_component_names_are_stable():
    """Class names must stay stable for saved flows."""
    assert BowmarkLibraryComponent.__name__ == "BowmarkLibraryComponent"
    assert BowmarkRunComponent.__name__ == "BowmarkRunComponent"


def test_library_sends_query_and_bearer(library):
    mock_get = MagicMock(return_value=_response("GET", LIBRARY_URL, text=LIBRARY_TEXT))
    with patch(GET_PATCH_TARGET, mock_get):
        message = library.bowmark_get_library()
    assert mock_get.call_args.args[0] == LIBRARY_URL
    assert mock_get.call_args.kwargs["params"] == {"query": "news.ycombinator.com"}
    headers = mock_get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"  # pragma: allowlist secret
    assert headers["User-Agent"] == "langflow-bowmark-bundle"
    assert message.text == LIBRARY_TEXT


def test_library_missing_key_makes_no_request(library):
    library.bowmark_api_key = ""
    mock_get = MagicMock()
    with patch(GET_PATCH_TARGET, mock_get):
        message = library.bowmark_get_library()
    mock_get.assert_not_called()
    assert "Bowmark API key is required" in message.text


def test_library_surfaces_api_error(library):
    mock_get = MagicMock(return_value=_response("GET", LIBRARY_URL, 401, json={"error": "invalid api key"}))
    with patch(GET_PATCH_TARGET, mock_get):
        message = library.bowmark_get_library()
    assert message.text == "Bowmark API error 401: invalid api key"


def test_run_posts_script(run):
    mock_post = MagicMock(return_value=_response("POST", RUN_URL, json=RUN_OK))
    with patch(POST_PATCH_TARGET, mock_post):
        data = run.bowmark_run()
    assert mock_post.call_args.args[0] == RUN_URL
    assert mock_post.call_args.kwargs["json"] == {"script": "return 1"}
    assert mock_post.call_args.kwargs["timeout"] == 60
    assert data.data["result"] == RUN_OK["result"]
    assert data.data["run_id"] == "run-123"
    assert data.data["logs"] == ["fetched 1"]
    assert "Story one" in data.text


def test_run_string_result_is_text(run):
    payload = {**RUN_OK, "result": "plain answer"}
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response("POST", RUN_URL, json=payload))):
        data = run.bowmark_run()
    assert data.text == "plain answer"


def test_run_failed_run_is_error_row(run):
    payload = {"ok": False, "status": "error", "result": None, "error": "boom", "runId": "run-9"}
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response("POST", RUN_URL, json=payload))):
        data = run.bowmark_run()
    assert data.data["error"] == "Bowmark run failed: boom (runId run-9)"


def test_run_empty_script_makes_no_request(run):
    run.script = "   "
    mock_post = MagicMock()
    with patch(POST_PATCH_TARGET, mock_post):
        data = run.bowmark_run()
    mock_post.assert_not_called()
    assert data.data["error"] == "Script is required."


def test_run_missing_key_makes_no_request(run):
    run.bowmark_api_key = ""
    mock_post = MagicMock()
    with patch(POST_PATCH_TARGET, mock_post):
        data = run.bowmark_run()
    mock_post.assert_not_called()
    assert "Bowmark API key is required" in data.data["error"]


def test_run_transport_error(run):
    with patch(POST_PATCH_TARGET, MagicMock(side_effect=httpx.HTTPError("down"))):
        data = run.bowmark_run()
    assert data.data["error"] == "down"


def test_run_non_json_error_falls_back_to_reason(run):
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response("POST", RUN_URL, 502, text="bad"))):
        data = run.bowmark_run()
    assert data.data["error"] == "Bowmark API error 502: Bad Gateway"


def test_run_non_object_payload(run):
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response("POST", RUN_URL, json=["x"]))):
        data = run.bowmark_run()
    assert "unexpected response" in data.data["error"]


def test_tool_names_are_bowmark_specific():
    """Agent-facing tool names must not collide with other components."""
    lib = BowmarkLibraryComponent(bowmark_api_key="test-key")  # pragma: allowlist secret
    runner = BowmarkRunComponent(bowmark_api_key="test-key", timeout=60)  # pragma: allowlist secret
    assert [t.name for t in asyncio.run(lib.to_toolkit())] == ["bowmark_get_library"]
    tools = asyncio.run(runner.to_toolkit())
    assert [t.name for t in tools] == ["bowmark_run"]
    mock_post = MagicMock(return_value=_response("POST", RUN_URL, json=RUN_OK))
    with patch(POST_PATCH_TARGET, mock_post):
        output = asyncio.run(tools[0].ainvoke({"script": "return 2"}))
    assert mock_post.call_args.kwargs["json"] == {"script": "return 2"}
    assert "Story one" in str(output)
