"""Tests for upstream / provider error classification.

Covers ``classify_component_error`` and its helper functions introduced to
propagate meaningful HTTP status codes from component failures instead of
always returning 500.
"""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from langflow.exceptions.api import (
    ExceptionBody,
    _exc_status_code,
    _has_upstream_indicator,
    _walk_cause_chain,
    classify_component_error,
)

# ------------------------------------------------------------------ helpers --


def _make_exc_with_status(status_code: int, msg: str = "err") -> Exception:
    """Return an exception carrying a ``status_code`` attribute."""
    exc = Exception(msg)
    exc.status_code = status_code  # type: ignore[attr-defined]
    return exc


def _make_exc_with_response(status_code: int, msg: str = "err") -> Exception:
    """Return an exception whose ``.response.status_code`` is set."""
    exc = Exception(msg)
    exc.response = SimpleNamespace(status_code=status_code)  # type: ignore[attr-defined]
    return exc


def _chain(outer_msg: str, cause: BaseException) -> BaseException:
    """Build ``ValueError(outer_msg)`` chained to *cause* via ``raise … from``."""
    try:
        raise ValueError(outer_msg) from cause
    except ValueError as wrapper:
        return wrapper


def _make_sdk_timeout(msg: str = "Request timed out") -> Exception:
    """Return a timeout exception that looks like it came from an SDK."""
    exc = Exception(msg)
    exc.request = SimpleNamespace(url="https://api.openai.com/v1/chat")  # type: ignore[attr-defined]
    return exc


# ======================================================================== #
#  _exc_status_code
# ======================================================================== #


class TestExcStatusCode:
    def test_status_code_attribute(self):
        exc = _make_exc_with_status(429)
        assert _exc_status_code(exc) == 429

    def test_code_attribute(self):
        exc = Exception("err")
        exc.code = 503  # type: ignore[attr-defined]
        assert _exc_status_code(exc) == 503

    def test_http_status_attribute(self):
        exc = Exception("err")
        exc.http_status = 401  # type: ignore[attr-defined]
        assert _exc_status_code(exc) == 401

    def test_response_status_code(self):
        exc = _make_exc_with_response(502)
        assert _exc_status_code(exc) == 502

    def test_no_status_code(self):
        assert _exc_status_code(Exception("plain")) is None

    def test_non_int_status_code_ignored(self):
        exc = Exception("err")
        exc.status_code = "429"  # type: ignore[attr-defined]
        assert _exc_status_code(exc) is None


# ======================================================================== #
#  _walk_cause_chain
# ======================================================================== #


class TestWalkCauseChain:
    def test_single_exception(self):
        exc = ValueError("only one")
        chain = _walk_cause_chain(exc)
        assert chain == [exc]

    def test_chained_cause(self):
        root = RuntimeError("root")
        wrapper = _chain("wrapper", root)
        chain = _walk_cause_chain(wrapper)
        assert len(chain) == 2
        assert chain[0] is wrapper
        assert chain[1] is root

    def test_deep_chain(self):
        a = RuntimeError("a")
        b = _chain("b", a)
        c = _chain("c", b)
        chain = _walk_cause_chain(c)
        assert len(chain) == 3

    def test_circular_chain_protection(self):
        """Ensure the walker doesn't loop on a pathological circular chain."""
        a = Exception("a")
        b = Exception("b")
        a.__cause__ = b
        b.__cause__ = a  # circular
        chain = _walk_cause_chain(a)
        assert len(chain) == 2


# ======================================================================== #
#  _has_upstream_indicator
# ======================================================================== #


class TestHasUpstreamIndicator:
    def test_plain_exception_has_no_indicator(self):
        assert _has_upstream_indicator(Exception("err")) is False

    def test_response_attribute(self):
        exc = Exception("err")
        exc.response = SimpleNamespace(status_code=200)  # type: ignore[attr-defined]
        assert _has_upstream_indicator(exc) is True

    def test_request_attribute(self):
        exc = Exception("err")
        exc.request = SimpleNamespace(url="https://example.com")  # type: ignore[attr-defined]
        assert _has_upstream_indicator(exc) is True

    def test_headers_attribute(self):
        exc = Exception("err")
        exc.headers = {"x-request-id": "abc"}  # type: ignore[attr-defined]
        assert _has_upstream_indicator(exc) is True

    def test_metadata_attribute(self):
        exc = Exception("err")
        exc.metadata = {"key": "val"}  # type: ignore[attr-defined]
        assert _has_upstream_indicator(exc) is True

    def test_none_valued_attribute_ignored(self):
        exc = Exception("err")
        exc.response = None  # type: ignore[attr-defined]
        assert _has_upstream_indicator(exc) is False


# ======================================================================== #
#  classify_component_error  —  Phase 1: explicit HTTP status codes
# ======================================================================== #


class TestClassifyPhase1StatusCodes:
    """Phase 1 detection: the exception (or its cause) carries an HTTP code."""

    def test_429_on_exception(self):
        exc = _make_exc_with_status(429, "Rate limit exceeded")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.TOO_MANY_REQUESTS
        assert source == "upstream"

    def test_429_on_chained_cause(self):
        root = _make_exc_with_status(429, "too many requests")
        wrapper = _chain("Error running graph: too many requests", root)
        status_code, source = classify_component_error(wrapper)
        assert status_code == HTTPStatus.TOO_MANY_REQUESTS
        assert source == "upstream"

    def test_401_returns_502(self):
        exc = _make_exc_with_status(401, "Unauthorized")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.BAD_GATEWAY
        assert source == "upstream"

    def test_403_returns_502(self):
        exc = _make_exc_with_status(403, "Forbidden")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.BAD_GATEWAY
        assert source == "upstream"

    def test_408_returns_504(self):
        exc = _make_exc_with_status(408, "Request Timeout")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.GATEWAY_TIMEOUT
        assert source == "upstream"

    def test_generic_4xx_returns_422(self):
        exc = _make_exc_with_status(422, "Unprocessable Entity")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert source == "upstream"

    def test_400_returns_422(self):
        exc = _make_exc_with_status(400, "Bad Request from provider")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert source == "upstream"

    def test_500_upstream_returns_502(self):
        exc = _make_exc_with_status(500, "Internal Server Error from provider")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.BAD_GATEWAY
        assert source == "upstream"

    def test_503_upstream_returns_502(self):
        exc = _make_exc_with_status(503, "Service Unavailable")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.BAD_GATEWAY
        assert source == "upstream"

    def test_response_status_code_detected(self):
        exc = _make_exc_with_response(429, "rate limited")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.TOO_MANY_REQUESTS
        assert source == "upstream"


# ======================================================================== #
#  classify_component_error  —  Phase 2: heuristic / pattern matching
# ======================================================================== #


class TestClassifyPhase2Patterns:
    """Phase 2 detection: no explicit status code, fallback to patterns."""

    # -- Rate-limit patterns --

    @pytest.mark.parametrize(
        "msg",
        [
            "Error: Rate limit exceeded",
            "Too many requests, please retry after 60s",
            "Quota exceeded for model gpt-4o",
            "tokens per min limit reached",
            "requests per min exceeded",
        ],
    )
    def test_rate_limit_messages(self, msg: str):
        exc = Exception(msg)
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.TOO_MANY_REQUESTS
        assert source == "upstream"

    def test_rate_limit_class_name(self):
        class RateLimitError(Exception):
            pass

        exc = RateLimitError("slow down")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.TOO_MANY_REQUESTS
        assert source == "upstream"

    # -- Auth patterns --

    @pytest.mark.parametrize(
        "msg",
        [
            "Invalid API key provided",
            "Authentication failed",
            "Unauthorized access",
            "Permission denied for resource",
            "Access denied",
            "Incorrect API key",
        ],
    )
    def test_auth_messages(self, msg: str):
        exc = Exception(msg)
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.BAD_GATEWAY
        assert source == "upstream"

    def test_auth_class_name(self):
        class AuthenticationError(Exception):
            pass

        exc = AuthenticationError("bad key")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.BAD_GATEWAY
        assert source == "upstream"

    # -- Connection patterns --

    @pytest.mark.parametrize(
        "msg",
        [
            "Connection error: refused",
            "Connection refused",
            "Connection reset by peer",
            "Connection aborted",
            "Name resolution failed",
            "Host unreachable",
        ],
    )
    def test_connection_messages(self, msg: str):
        exc = Exception(msg)
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.BAD_GATEWAY
        assert source == "upstream"

    @pytest.mark.parametrize("cls_name", ["APIConnectionError", "ConnectionError", "ConnectError"])
    def test_connection_class_names(self, cls_name: str):
        exc_cls = type(cls_name, (Exception,), {})
        exc = exc_cls("connection lost")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.BAD_GATEWAY
        assert source == "upstream"


# ======================================================================== #
#  classify_component_error  —  Timeout guarding
# ======================================================================== #


class TestClassifyTimeoutGuard:
    """Builtin TimeoutError must NOT be classified as upstream.

    Only SDK-specific timeout classes or timeout messages with upstream
    indicators should be classified as upstream.
    """

    def test_builtin_timeout_error_is_internal(self):
        """Plain ``TimeoutError`` is an internal error, not upstream."""
        exc = TimeoutError("internal task timed out")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert source == "internal"

    def test_asyncio_timeout_error_is_internal(self):
        """``asyncio.TimeoutError`` is the same as ``TimeoutError`` in modern Python."""
        exc = asyncio.TimeoutError()
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert source == "internal"

    def test_sdk_api_timeout_error_is_upstream(self):
        """An exception named ``APITimeoutError`` is unambiguously upstream."""

        class APITimeoutError(Exception):
            pass

        exc = APITimeoutError("request timed out")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.GATEWAY_TIMEOUT
        assert source == "upstream"

    def test_sdk_read_timeout_is_upstream(self):
        class ReadTimeout(Exception):  # noqa: N818
            pass

        exc = ReadTimeout("read timed out")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.GATEWAY_TIMEOUT
        assert source == "upstream"

    def test_sdk_connect_timeout_is_upstream(self):
        class ConnectTimeout(Exception):  # noqa: N818
            pass

        exc = ConnectTimeout("connect timed out")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.GATEWAY_TIMEOUT
        assert source == "upstream"

    def test_timeout_message_with_sdk_indicator_is_upstream(self):
        """A timeout message from an exception with SDK attributes -> upstream."""
        exc = _make_sdk_timeout("Request timed out after 30s")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.GATEWAY_TIMEOUT
        assert source == "upstream"

    def test_timeout_message_without_sdk_indicator_is_internal(self):
        """A timeout message from a plain exception (no SDK attrs) -> internal."""
        exc = Exception("Operation timed out")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert source == "internal"

    def test_deadline_exceeded_with_sdk_indicator(self):
        exc = Exception("Deadline exceeded waiting for response")
        exc.response = SimpleNamespace(status_code=200)  # type: ignore[attr-defined]
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.GATEWAY_TIMEOUT
        assert source == "upstream"

    def test_deadline_exceeded_without_sdk_indicator(self):
        exc = Exception("Deadline exceeded")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert source == "internal"

    def test_chained_timeout_with_sdk_cause(self):
        """Timeout message on wrapper, SDK indicator on chained cause -> upstream."""
        sdk_cause = Exception("underlying timeout")
        sdk_cause.request = SimpleNamespace(url="https://api.openai.com")  # type: ignore[attr-defined]
        wrapper = _chain("Error running graph: request timed out", sdk_cause)
        status_code, source = classify_component_error(wrapper)
        assert status_code == HTTPStatus.GATEWAY_TIMEOUT
        assert source == "upstream"


# ======================================================================== #
#  classify_component_error  —  Default / internal
# ======================================================================== #


class TestClassifyDefault:
    def test_plain_exception_is_internal(self):
        exc = Exception("something broke")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert source == "internal"

    def test_value_error_is_internal(self):
        exc = ValueError("bad value")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert source == "internal"

    def test_key_error_is_internal(self):
        exc = KeyError("missing_key")
        status_code, source = classify_component_error(exc)
        assert status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert source == "internal"


# ======================================================================== #
#  classify_component_error  —  Realistic end-to-end chains
# ======================================================================== #


class TestClassifyRealisticChains:
    """Simulate the real exception chain: component error → graph ValueError."""

    def test_openai_rate_limit_chain(self):
        """Simulate openai.RateLimitError chained to graph ValueError."""

        class RateLimitError(Exception):
            pass

        root = RateLimitError("You exceeded your current quota")
        root.status_code = 429  # type: ignore[attr-defined]
        wrapper = _chain("Error running graph (component: OpenAIModel): You exceeded your current quota", root)
        status_code, source = classify_component_error(wrapper)
        assert status_code == HTTPStatus.TOO_MANY_REQUESTS
        assert source == "upstream"

    def test_openai_auth_error_chain(self):
        class AuthenticationError(Exception):
            pass

        root = AuthenticationError("Incorrect API key provided")
        root.status_code = 401  # type: ignore[attr-defined]
        wrapper = _chain("Error running graph (component: OpenAIModel): Incorrect API key provided", root)
        status_code, source = classify_component_error(wrapper)
        assert status_code == HTTPStatus.BAD_GATEWAY
        assert source == "upstream"

    def test_httpx_status_error_chain(self):
        """Simulate httpx.HTTPStatusError with .response.status_code."""
        root = Exception("Server error")
        root.response = SimpleNamespace(status_code=503)  # type: ignore[attr-defined]
        wrapper = _chain("Error running graph: Server error", root)
        status_code, source = classify_component_error(wrapper)
        assert status_code == HTTPStatus.BAD_GATEWAY
        assert source == "upstream"

    def test_generic_internal_error_chain(self):
        root = TypeError("unsupported operand type(s)")
        wrapper = _chain("Error running graph (component: TextSplitter): unsupported operand type(s)", root)
        status_code, source = classify_component_error(wrapper)
        assert status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert source == "internal"


# ======================================================================== #
#  ExceptionBody.source field
# ======================================================================== #


class TestExceptionBodySource:
    def test_source_field_defaults_to_none(self):
        body = ExceptionBody(message="err")
        assert body.source is None

    def test_source_field_set(self):
        body = ExceptionBody(message="err", source="upstream")
        assert body.source == "upstream"

    def test_source_serialised_in_json(self):
        body = ExceptionBody(message="err", source="upstream")
        data = body.model_dump()
        assert data["source"] == "upstream"

    def test_source_absent_in_json_when_none(self):
        body = ExceptionBody(message="err")
        data = body.model_dump()
        assert data["source"] is None


# ======================================================================== #
#  APIException.build_exception_body with source
# ======================================================================== #


class TestBuildExceptionBodySource:
    def test_source_kwarg_included(self):
        from langflow.exceptions.api import APIException

        body = APIException.build_exception_body(Exception("err"), flow=None, source="upstream")
        assert body.source == "upstream"

    def test_source_kwarg_omitted_defaults_none(self):
        from langflow.exceptions.api import APIException

        body = APIException.build_exception_body(Exception("err"), flow=None)
        assert body.source is None

    def test_backward_compat_no_source(self):
        """Existing callers that don't pass source still work."""
        from langflow.exceptions.api import APIException

        body = APIException.build_exception_body("simple string", flow=None)
        assert body.message == "simple string"
        assert body.source is None
