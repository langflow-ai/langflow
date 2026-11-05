"""Unit tests for the TestMu AI components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the
real URLs, query parameters, Basic auth and error handling of the client.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.testmuai.testmuai_builds import TestMuAIBuildsComponent
from lfx_bundles.testmuai.testmuai_common import API_BASE_URL, MAX_LIMIT
from lfx_bundles.testmuai.testmuai_sessions import TestMuAISessionsComponent

USERNAME = "test-user"
# Placeholder credential for the mocked API (not a real key).
ACCESS_KEY = "test-testmuai-access-key-placeholder"  # pragma: allowlist secret

BUILDS = [
    {"build_id": 101, "name": "Nightly regression", "status_ind": "completed", "dashboard_url": "https://x/101"},
    {"build_id": 102, "name": "", "status_ind": "running"},
]
SESSIONS = [
    {
        "test_id": "T1",
        "build_id": 101,
        "name": "checkout flow",
        "status_ind": "failed",
        "browser": "chrome",
        "version": "130",
        "platform": "Windows 11",
        "remark": "Element not found",
    },
    {"test_id": "T2", "build_id": 101, "name": "login", "status_ind": "passed"},
]


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _builds(**values) -> TestMuAIBuildsComponent:
    component = TestMuAIBuildsComponent()
    component.set(**{"username": USERNAME, "access_key": ACCESS_KEY, **values})
    return component


def _sessions(**values) -> TestMuAISessionsComponent:
    component = TestMuAISessionsComponent()
    component.set(**{"username": USERNAME, "access_key": ACCESS_KEY, **values})
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [TestMuAIBuildsComponent, TestMuAISessionsComponent])
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [TestMuAIBuildsComponent, TestMuAISessionsComponent])
def test_metadata(component_class: type[Component]) -> None:
    component = component_class()
    assert component.icon == "TestMuAI"
    assert "testmuai.com" in component.documentation
    access_key = next(inp for inp in component_class.inputs if inp.name == "access_key")
    assert access_key.required is True


@pytest.mark.unit
class TestBuilds:
    def test_lists_builds_with_basic_auth(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"data": BUILDS})) as request:
            data = _builds().list_builds()

        method, url = request.call_args.args
        assert method == "GET"
        assert url == f"{API_BASE_URL}/automation/api/v1/builds"
        assert request.call_args.kwargs["auth"] == (USERNAME, ACCESS_KEY)
        assert request.call_args.kwargs["params"] == {"limit": 10}
        assert data[0].text == "Nightly regression (build 101): completed"
        assert data[1].text == "Untitled build (build 102): running"
        assert data[0].data["dashboard_url"] == "https://x/101"

    def test_status_and_limit_are_sent(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"data": []})) as request:
            _builds(build_status=" error ", limit=500).list_builds()

        assert request.call_args.kwargs["params"] == {"limit": MAX_LIMIT, "status": "error"}

    def test_missing_credentials_make_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _builds(access_key="  ").list_builds()

        request.assert_not_called()
        assert data[0].data["error"] == "Enter your TestMu AI username and access key."

    def test_rejected_credentials_are_reported_and_key_is_redacted(self) -> None:
        body = {"message": f"Access denied for {ACCESS_KEY}"}
        with patch("httpx.Client.request", return_value=_response(401, json_body=body)):
            data = _builds().list_builds()

        error = data[0].data["error"]
        assert "rejected the username or access key (401)" in error
        assert ACCESS_KEY not in error

    def test_non_json_body_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(text="<html>")):
            data = _builds().list_builds()

        assert "not JSON" in data[0].data["error"]

    def test_timeout_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ReadTimeout("slow")):
            data = _builds(timeout=5).list_builds()

        assert data[0].data["error"] == "TestMu AI request timed out after 5 seconds."

    def test_missing_data_list_returns_no_rows(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"status": "success"})):
            assert _builds().list_builds() == []

    def test_dataframe_output(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"data": BUILDS})):
            frame = _builds().builds_dataframe()

        assert list(frame["build_id"]) == [101, 102]


@pytest.mark.unit
class TestSessions:
    def test_lists_sessions_for_a_build(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"data": SESSIONS})) as request:
            data = _sessions(build_id=" 101 ", session_status="failed", limit=0).list_sessions()

        assert request.call_args.args[1] == f"{API_BASE_URL}/automation/api/v1/sessions"
        assert request.call_args.kwargs["params"] == {"limit": 1, "build_id": "101", "status": "failed"}
        assert data[0].text == "checkout flow: failed (chrome 130 on Windows 11) - Element not found"
        assert data[1].text == "login: passed"

    def test_non_numeric_build_id_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _sessions(build_id="abc").list_sessions()

        request.assert_not_called()
        assert data[0].data["error"] == "Build ID must be a number."

    def test_server_error_is_reported(self) -> None:
        with patch("httpx.Client.request", return_value=_response(500, text="upstream failed")):
            data = _sessions().list_sessions()

        assert data[0].data["error"] == "TestMu AI API error (500): upstream failed"

    def test_unexpected_shape_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"data": "nope"})):
            data = _sessions().list_sessions()

        assert data[0].data["error"] == "TestMu AI API returned an unexpected response shape."
