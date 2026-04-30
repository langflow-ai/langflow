"""Tests for the exception formatter that surfaces API error details to the UI.

Bug pre-existing in events.py — when an LLM provider returns a structured error
(IBM watsonx 429 with `body={"errors": [...]}`, OpenAI/Anthropic with
`body={"error": {"message": ...}}`), the UI used to show only `str(exc)` which
is generic ("Failure during achat."). The real error message — "consumption_limit_reached:
the total number of free concurrent requests has reached its limit 10" — was
buried in `.body` and only visible in backend logs.
"""

from typing import Any

from lfx.base.agents.exception_formatting import format_exception_for_message


# ---- IBM watsonx shape: body = {"errors": [{"code": ..., "message": ...}]} ----


def test_should_extract_message_from_ibm_watsonx_429_body() -> None:
    """IBM watsonx returns: {'errors': [{'code': 'consumption_limit_reached', 'message': '...'}]}"""

    class _ApiRequestFailure(Exception):
        def __init__(self) -> None:
            super().__init__("Failure during achat.")
            self.status_code = 429
            self.body = {
                "errors": [
                    {
                        "code": "consumption_limit_reached",
                        "message": (
                            "The usage limit for the current plan has been reached: "
                            "the total number of free concurrent requests for model "
                            "meta-llama/llama-3-2-11b-vision-instruct has reached its limit 10. "
                            "Please try again later"
                        ),
                    }
                ],
            }

    formatted = format_exception_for_message(_ApiRequestFailure())

    assert "consumption_limit_reached" in formatted or "limit 10" in formatted
    assert "Failure during achat" in formatted
    assert "429" in formatted


def test_should_concatenate_multiple_error_messages_when_body_has_many() -> None:
    class _Exc(Exception):
        def __init__(self) -> None:
            super().__init__("multi error")
            self.body = {
                "errors": [
                    {"message": "first error"},
                    {"message": "second error"},
                ],
            }

    formatted = format_exception_for_message(_Exc())

    assert "first error" in formatted
    assert "second error" in formatted


# ---- OpenAI / Anthropic shape: body = {"error": {"message": ...}} ----


def test_should_extract_message_from_openai_style_error_body() -> None:
    """OpenAI/Anthropic shape: {'error': {'message': '...', 'type': '...'}}"""

    class _Exc(Exception):
        def __init__(self) -> None:
            super().__init__("Bad Request")
            self.status_code = 400
            self.body = {
                "error": {
                    "message": "You exceeded your current quota.",
                    "type": "insufficient_quota",
                }
            }

    formatted = format_exception_for_message(_Exc())

    assert "exceeded your current quota" in formatted
    assert "Bad Request" in formatted


# ---- Falls back to response.json() when body attribute is absent ----


def test_should_extract_message_from_response_json_when_body_attr_absent() -> None:
    class _FakeResponse:
        def json(self) -> dict[str, Any]:
            return {"error": {"message": "missing API key"}}

    class _Exc(Exception):
        def __init__(self) -> None:
            super().__init__("Authentication failed")
            self.response = _FakeResponse()

    formatted = format_exception_for_message(_Exc())

    assert "missing API key" in formatted


# ---- Robustness: never crash on unusual exception shapes ----


def test_should_return_string_form_when_exception_has_no_structured_body() -> None:
    formatted = format_exception_for_message(ValueError("plain error"))

    assert formatted == "plain error"


def test_should_return_type_name_when_exception_has_empty_message() -> None:
    formatted = format_exception_for_message(RuntimeError())

    assert "RuntimeError" in formatted


def test_should_not_crash_when_body_is_not_a_dict() -> None:
    class _Exc(Exception):
        def __init__(self) -> None:
            super().__init__("weird")
            self.body = "this is a string body"

    # Should not raise — degrade gracefully.
    formatted = format_exception_for_message(_Exc())
    assert "weird" in formatted


def test_should_not_crash_when_response_json_raises() -> None:
    class _BadResponse:
        def json(self) -> dict:
            msg = "not parseable"
            raise ValueError(msg)

    class _Exc(Exception):
        def __init__(self) -> None:
            super().__init__("transient")
            self.response = _BadResponse()

    formatted = format_exception_for_message(_Exc())
    assert "transient" in formatted


def test_should_not_duplicate_main_text_when_api_message_is_a_substring() -> None:
    """If the str(exc) already contains the API message, don't append it again."""

    class _Exc(Exception):
        def __init__(self) -> None:
            super().__init__("rate_limit_exceeded: too many requests")
            self.body = {"error": {"message": "too many requests"}}

    formatted = format_exception_for_message(_Exc())

    # "too many requests" should appear only once.
    assert formatted.count("too many requests") == 1
