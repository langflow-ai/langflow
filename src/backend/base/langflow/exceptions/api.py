from __future__ import annotations

import re
from http import HTTPStatus
from typing import TYPE_CHECKING

from fastapi import HTTPException
from pydantic import BaseModel

from langflow.api.utils import get_suggestion_message
from langflow.services.database.models.flow.utils import get_outdated_components

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow


class InvalidChatInputError(Exception):
    pass


class WorkflowExecutionError(Exception):
    """Base exception for workflow execution errors."""


class WorkflowTimeoutError(WorkflowExecutionError):
    """Workflow execution timeout."""


class WorkflowValidationError(WorkflowExecutionError):
    """Workflow validation error (e.g., invalid flow data, graph build failure)."""


class WorkflowQueueFullError(WorkflowExecutionError):
    """Raised when the background task queue is full."""


class WorkflowResourceError(WorkflowExecutionError):
    """Raised when the server is out of memory or other resources."""


class WorkflowServiceUnavailableError(WorkflowExecutionError):
    """Raised when the task queue service is unavailable (e.g., broker down)."""


# --------------------------------------------------------------------------- #
# Upstream / provider error classification
# --------------------------------------------------------------------------- #

_RATE_LIMIT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"rate.?limit", re.IGNORECASE),
    re.compile(r"too many requests", re.IGNORECASE),
    re.compile(r"quota exceeded", re.IGNORECASE),
    re.compile(r"tokens per min", re.IGNORECASE),
    re.compile(r"requests per min", re.IGNORECASE),
]

_AUTH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"invalid.?api.?key", re.IGNORECASE),
    re.compile(r"authentication", re.IGNORECASE),
    re.compile(r"unauthorized", re.IGNORECASE),
    re.compile(r"permission denied", re.IGNORECASE),
    re.compile(r"access denied", re.IGNORECASE),
    re.compile(r"Incorrect API key", re.IGNORECASE),
]

_TIMEOUT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"timed?\s*out", re.IGNORECASE),
    re.compile(r"deadline.?exceeded", re.IGNORECASE),
    re.compile(r"read timeout", re.IGNORECASE),
    re.compile(r"connect timeout", re.IGNORECASE),
]

_CONNECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"connection.?(error|refused|reset|aborted)", re.IGNORECASE),
    re.compile(r"name.?resolution", re.IGNORECASE),
    re.compile(r"unreachable", re.IGNORECASE),
]


def _exc_status_code(exc: BaseException) -> int | None:
    """Extract an HTTP status code from an exception if it carries one."""
    for attr in ("status_code", "code", "http_status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
    return None


def _walk_cause_chain(exc: BaseException) -> list[BaseException]:
    """Collect the full __cause__ / __context__ chain of an exception."""
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


# SDK-specific timeout class names that are unambiguously from an upstream
# provider.  Built-in ``TimeoutError`` / ``asyncio.TimeoutError`` are
# intentionally excluded because they can be raised by Langflow's own
# internal task management and do not indicate an upstream failure.
_SDK_TIMEOUT_CLASSES: set[str] = {"APITimeoutError", "ReadTimeout", "ConnectTimeout"}

# Attributes that indicate an exception originated from an HTTP SDK rather
# than from internal Python / asyncio code.
_UPSTREAM_INDICATOR_ATTRS: tuple[str, ...] = ("response", "headers", "request", "metadata")


def _has_upstream_indicator(exc: BaseException) -> bool:
    """Return True if *exc* carries attributes typical of an HTTP SDK error."""
    return any(getattr(exc, attr, None) is not None for attr in _UPSTREAM_INDICATOR_ATTRS)


def classify_component_error(exc: BaseException) -> tuple[int, str]:
    """Inspect an exception's cause chain and return (http_status, source).

    Returns:
        A tuple of (status_code, source) where *source* is one of:
        ``"upstream"`` for errors originating from an external provider /
        API, or ``"internal"`` for errors within Langflow itself.
    """
    chain = _walk_cause_chain(exc)

    # --- Phase 1: look for an explicit HTTP status code on the exception ---
    for link in chain:
        code = _exc_status_code(link)
        if code is None:
            continue
        if code == HTTPStatus.TOO_MANY_REQUESTS:
            return HTTPStatus.TOO_MANY_REQUESTS, "upstream"
        if code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
            return HTTPStatus.BAD_GATEWAY, "upstream"
        if code == HTTPStatus.REQUEST_TIMEOUT:
            return HTTPStatus.GATEWAY_TIMEOUT, "upstream"
        if HTTPStatus.BAD_REQUEST <= code < HTTPStatus.INTERNAL_SERVER_ERROR:
            return HTTPStatus.UNPROCESSABLE_ENTITY, "upstream"
        if HTTPStatus.INTERNAL_SERVER_ERROR <= code < 600:  # noqa: PLR2004
            return HTTPStatus.BAD_GATEWAY, "upstream"

    # --- Phase 2: heuristic pattern / class-name matching -----------------
    all_messages = " ".join(str(link) for link in chain)
    cls_names = {type(link).__name__ for link in chain}

    if any(p.search(all_messages) for p in _RATE_LIMIT_PATTERNS) or "RateLimitError" in cls_names:
        return HTTPStatus.TOO_MANY_REQUESTS, "upstream"
    if any(p.search(all_messages) for p in _AUTH_PATTERNS) or "AuthenticationError" in cls_names:
        return HTTPStatus.BAD_GATEWAY, "upstream"

    # Timeout: only classify as upstream when the exception is from an SDK
    # (has response/request/headers) or uses an SDK-specific class name.
    # Plain ``TimeoutError`` / ``asyncio.TimeoutError`` are internal.
    if cls_names & _SDK_TIMEOUT_CLASSES:
        return HTTPStatus.GATEWAY_TIMEOUT, "upstream"
    if any(p.search(all_messages) for p in _TIMEOUT_PATTERNS) and any(_has_upstream_indicator(link) for link in chain):
        return HTTPStatus.GATEWAY_TIMEOUT, "upstream"

    if any(p.search(all_messages) for p in _CONNECTION_PATTERNS) or cls_names & {
        "APIConnectionError",
        "ConnectionError",
        "ConnectError",
    }:
        return HTTPStatus.BAD_GATEWAY, "upstream"

    return HTTPStatus.INTERNAL_SERVER_ERROR, "internal"


class ExceptionBody(BaseModel):
    message: str | list[str]
    traceback: str | list[str] | None = None
    description: str | list[str] | None = None
    code: str | None = None
    suggestion: str | list[str] | None = None
    source: str | None = None


class APIException(HTTPException):
    def __init__(self, exception: Exception, flow: Flow | None = None, status_code: int = 500):
        body = self.build_exception_body(exception, flow)
        super().__init__(status_code=status_code, detail=body.model_dump_json())

    @staticmethod
    def build_exception_body(
        exc: str | list[str] | Exception, flow: Flow | None, *, source: str | None = None
    ) -> ExceptionBody:
        body: dict = {"message": str(exc)}
        if source is not None:
            body["source"] = source
        if flow:
            outdated_components = get_outdated_components(flow)
            if outdated_components:
                body["suggestion"] = get_suggestion_message(outdated_components)
        return ExceptionBody(**body)
