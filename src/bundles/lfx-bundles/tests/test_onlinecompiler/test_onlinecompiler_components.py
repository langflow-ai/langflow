"""Unit tests for the OnlineCompiler.io components with mocked HTTP calls.

Requests are intercepted at ``httpx.AsyncClient.post``, so the tests exercise the real
paths, headers, JSON bodies and error handling of the client.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.onlinecompiler.onlinecompiler_common import API_BASE_URL, OnlineCompilerAPIError, parse_tests
from lfx_bundles.onlinecompiler.onlinecompiler_run_code import OnlineCompilerRunCodeComponent
from lfx_bundles.onlinecompiler.onlinecompiler_run_tests import OnlineCompilerRunTestsComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "oc_test_placeholder_key"  # pragma: allowlist secret

ALL_COMPONENTS = [OnlineCompilerRunCodeComponent, OnlineCompilerRunTestsComponent]

RUN_RESULT = {"output": "Hello, Ada!\n", "error": "", "status": "success", "exit_code": 0, "time": 0.02, "memory": 9000}
TESTS_RESULT = {
    "verdict": "wrong_answer",
    "score": 50,
    "passed": 1,
    "total": 2,
    "tests": [{"verdict": "accepted"}, {"verdict": "wrong_answer", "hidden": True}],
}
HELLO = "print(f'Hello, {input()}!')"
TESTS_JSON = '[{"input": "2 3", "expected_output": "5"}, {"input": "1 1", "expected_output": "2"}]'


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("POST", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _run_code(**values) -> OnlineCompilerRunCodeComponent:
    component = OnlineCompilerRunCodeComponent()
    component.set(**{"api_key": API_KEY, "compiler": "python-3.14", "source_code": HELLO, **values})
    return component


def _run_tests(**values) -> OnlineCompilerRunTestsComponent:
    component = OnlineCompilerRunTestsComponent()
    component.set(
        **{
            "api_key": API_KEY,
            "compiler": "python-3.14",
            "source_code": "a, b = map(int, input().split())\nprint(a + b)",
            "tests": TESTS_JSON,
            **values,
        }
    )
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
class TestMetadata:
    def test_inputs_do_not_shadow_component_attributes(self, component_class) -> None:
        shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
        assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"

    def test_metadata_and_required_key(self, component_class) -> None:
        component = component_class()
        assert component.icon == "SquareTerminal"
        assert "onlinecompiler.io" in component.documentation
        api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
        assert api_key.required is True

    def test_agent_fills_language_and_code_in_tool_mode(self, component_class) -> None:
        tool_inputs = {inp.name for inp in component_class.inputs if getattr(inp, "tool_mode", False)}
        assert {"compiler", "source_code"} <= tool_inputs
        assert "api_key" not in tool_inputs


@pytest.mark.unit
class TestRunCode:
    async def test_posts_code_and_input_and_sends_the_key(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_response(json_body=RUN_RESULT)) as post:
            result = await _run_code(stdin="Ada").run_code()

        assert post.call_args.args[0] == f"{API_BASE_URL}/api/run-code-sync/"
        assert post.call_args.kwargs["headers"]["Authorization"] == API_KEY
        assert post.call_args.kwargs["json"] == {
            "compiler": "python-3.14",
            "code": HELLO,
            "input": "Ada",
        }
        assert result.text == "Hello, Ada!\n"
        assert result.data["exit_code"] == 0

    async def test_empty_input_and_zero_time_limit_are_left_out(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_response(json_body=RUN_RESULT)) as post:
            await _run_code(stdin="", time_limit=0.0).run_code()
        assert set(post.call_args.kwargs["json"]) == {"compiler", "code"}

    async def test_time_limit_is_sent_when_set(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_response(json_body=RUN_RESULT)) as post:
            await _run_code(time_limit=5.0).run_code()
        assert post.call_args.kwargs["json"]["time_limit"] == 5.0

    async def test_stderr_and_exit_code_are_shown_when_the_program_fails(self) -> None:
        failed = {**RUN_RESULT, "output": "partial\n", "error": "Traceback: boom\n", "exit_code": 1}
        with patch("httpx.AsyncClient.post", return_value=_response(json_body=failed)):
            result = await _run_code().run_code()
        assert result.text == "partial\nstderr:\nTraceback: boom\nexit code: 1"

    async def test_missing_key_or_code_never_calls_the_api(self) -> None:
        with patch("httpx.AsyncClient.post") as post:
            no_key = await _run_code(api_key="").run_code()
            no_code = await _run_code(source_code="  ").run_code()
        post.assert_not_called()
        assert "API key" in no_key.text
        assert no_code.data["api_error"] == "Enter the code to run."


@pytest.mark.unit
class TestRunTests:
    async def test_posts_tests_checker_and_scoring(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_response(json_body=TESTS_RESULT)) as post:
            result = await _run_tests(checker="tokens", scoring="all_or_nothing").run_tests()

        assert post.call_args.args[0] == f"{API_BASE_URL}/api/run-tests/"
        body = post.call_args.kwargs["json"]
        assert body["tests"] == [{"input": "2 3", "expected_output": "5"}, {"input": "1 1", "expected_output": "2"}]
        assert body["checker"] == "tokens"
        assert body["scoring"] == "all_or_nothing"
        assert result.text.splitlines() == [
            "wrong_answer: 1 of 2 tests passed, score 50",
            "test 1: accepted",
            "test 2: wrong_answer (hidden)",
        ]
        assert result.data["score"] == 50

    async def test_invalid_tests_never_call_the_api(self) -> None:
        with patch("httpx.AsyncClient.post") as post:
            bad_json = await _run_tests(tests="not json").run_tests()
            empty = await _run_tests(tests="[]").run_tests()
        post.assert_not_called()
        assert "JSON array" in bad_json.text
        assert "non-empty" in empty.text


@pytest.mark.unit
class TestParseTests:
    def test_accepts_other_names_and_non_text_values(self) -> None:
        tests = parse_tests([{"input": 2, "expectedOutput": 4}, {"output": True}])
        assert tests == [{"input": "2", "expected_output": "4"}, {"input": "", "expected_output": "true"}]

    def test_a_test_without_expected_output_is_refused(self) -> None:
        with pytest.raises(OnlineCompilerAPIError, match="Test 1 has no expected_output"):
            parse_tests('[{"input": "1"}]')


@pytest.mark.unit
class TestErrors:
    @pytest.mark.parametrize(
        ("status", "body", "expected"),
        [
            (404, {"error": "Invalid API key"}, "did not find the API key"),
            (429, {"error": "Free plan allows 30 runs a minute"}, "plan limit reached (429): Free plan allows 30"),
            (400, {"error": "Unknown compiler: python-2"}, "API error (400): Unknown compiler"),
        ],
    )
    async def test_api_errors_are_returned_as_data(self, status, body, expected) -> None:
        with patch("httpx.AsyncClient.post", return_value=_response(status, json_body=body)):
            result = await _run_code().run_code()
        assert expected in result.text
        assert "api_error" in result.data

    async def test_the_key_is_redacted_from_error_details(self) -> None:
        body = {"error": f"bad key {API_KEY}"}
        with patch("httpx.AsyncClient.post", return_value=_response(401, json_body=body)):
            result = await _run_code().run_code()
        assert API_KEY not in result.text
        assert "***" in result.text

    async def test_non_json_error_page(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_response(502, text="<html>Bad gateway</html>")):
            result = await _run_tests().run_tests()
        assert "API error (502)" in result.text

    async def test_timeout_and_network_errors(self) -> None:
        with patch("httpx.AsyncClient.post", side_effect=httpx.ReadTimeout("slow")):
            slow = await _run_code(timeout=5.0).run_code()
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("refused")):
            down = await _run_code().run_code()
        assert "did not answer within 5 seconds" in slow.text
        assert "Could not reach the OnlineCompiler.io API: ConnectError" in down.text
