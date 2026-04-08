"""Framework-agnostic deployment exceptions for LFX deployment service.

Shared exception types for all deployment service implementations,
regardless of adapter.
"""

from __future__ import annotations

import re
from typing import NoReturn

from fastapi import status


class DeploymentServiceError(Exception):
    """Root exception for all deployment service failures.

    Both operational errors (:class:`DeploymentError`) and authentication
    or authorization errors (:class:`AuthenticationError`, :class:`AuthorizationError`)
    inherit from this class.
    Catch this only when you truly want to handle *every* deployment-related
    failure uniformly.
    """

    def __init__(self, message: str, *, error_code: str, cause: Exception | None = None):
        self.message = message
        self.error_code = error_code
        self.cause = cause
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause


class DeploymentError(DeploymentServiceError):
    """Base exception for deployment operation failures (non-auth)."""


class AuthenticationError(DeploymentServiceError):
    """Base exception for authentication failures.

    Intentionally a sibling of :class:`DeploymentError`, not a child.
    This ensures ``except DeploymentError`` will not accidentally swallow
    authentication failures, allowing API layers to return the correct
    HTTP status (401/403) separately from deployment errors (400/404/409/422).

    Please ensure that the message does not leak sensitive information.
    """


class AuthorizationError(DeploymentServiceError):
    """Base exception for authorization failures (authenticated but forbidden).

    Intentionally a sibling of :class:`DeploymentError`, not a child.
    This ensures ``except DeploymentError`` will not accidentally swallow
    authorization failures, allowing API layers to return status 403
    separately from deployment errors (400/404/409/422).

    Please ensure that the message does not leak sensitive information.
    """


class CredentialResolutionError(AuthenticationError):
    """Raised when credentials resolution fails.

    Please ensure that the message does not leak sensitive information.
    """

    def __init__(self, message: str = "Credentials resolution failed", *, cause: Exception | None = None):
        super().__init__(message, error_code="credentials_resolution_error", cause=cause)


class ResourceConflictError(DeploymentError):
    """Raised when a deployment conflict occurs."""

    def __init__(
        self,
        message: str = "Deployment conflict occurred",
        *,
        resource: str | None = None,
        resource_name: str | None = None,
        cause: Exception | None = None,
    ):
        self.resource = str(resource).strip().lower() if resource is not None else None
        self.resource_name = str(resource_name).strip() or None if resource_name is not None else None
        super().__init__(message, error_code="deployment_conflict", cause=cause)


# Backward-compatible alias; prefer ResourceConflictError in new code.
DeploymentConflictError = ResourceConflictError


class InvalidContentError(DeploymentError):
    """Raised when a deployment request entity is unprocessable."""

    def __init__(self, message: str = "Deployment request entity is unprocessable", *, cause: Exception | None = None):
        super().__init__(message, error_code="unprocessable_content_error", cause=cause)


class InvalidDeploymentOperationError(DeploymentError):
    """Raised when a deployment operation is invalid for current adapter semantics."""

    def __init__(self, message: str = "Invalid deployment operation", *, cause: Exception | None = None):
        super().__init__(message, error_code="invalid_deployment_operation", cause=cause)


class DeploymentSupportError(DeploymentError):
    """Raised when a known deployment type is unsupported by this adapter."""

    def __init__(
        self,
        message: str = "Deployment type is unsupported by this adapter",
        *,
        cause: Exception | None = None,
    ):
        super().__init__(message, error_code="unsupported_deployment_type", cause=cause)


class RateLimitError(DeploymentError):
    """Raised when provider/API rate limits deployment operations."""

    def __init__(self, message: str = "Deployment operation rate limited", *, cause: Exception | None = None):
        super().__init__(message, error_code="deployment_rate_limited", cause=cause)


class DeploymentTimeoutError(DeploymentError):
    """Raised when deployment operation times out."""

    def __init__(self, message: str = "Deployment operation timed out", *, cause: Exception | None = None):
        super().__init__(message, error_code="deployment_timeout", cause=cause)


class ServiceUnavailableError(DeploymentError):
    """Raised when upstream provider is temporarily unavailable."""

    def __init__(self, message: str = "Deployment provider is unavailable", *, cause: Exception | None = None):
        super().__init__(message, error_code="deployment_provider_unavailable", cause=cause)


class AuthSchemeError(AuthenticationError):
    """Raised when no matching authentication scheme was found.

    Please ensure that the message does not leak sensitive information.
    """

    def __init__(self, message: str = "No matching authentication scheme was found", *, cause: Exception | None = None):
        super().__init__(message, error_code="unsupported_auth_type", cause=cause)


class InvalidDeploymentTypeError(DeploymentError):
    """Raised when an input deployment type is malformed or not recognized."""

    def __init__(self, message: str = "Deployment type is malformed or unknown", *, cause: Exception | None = None):
        super().__init__(message, error_code="invalid_deployment_type", cause=cause)


class ResourceNotFoundError(DeploymentError):
    """Raised when a requested deployment-related resource is not found."""

    def __init__(
        self,
        message: str | None = None,
        *,
        resource_id: str | None = None,
        cause: Exception | None = None,
    ):
        self.resource_id = resource_id
        if message is None:
            message = "Resource not found"
            if resource_id:
                message = f"Resource not found: {resource_id}"
        super().__init__(message, error_code="resource_not_found", cause=cause)


class DeploymentNotFoundError(ResourceNotFoundError):
    """Raised when a deployment is not found."""

    def __init__(
        self,
        message: str | None = None,
        *,
        deployment_id: str | None = None,
        cause: Exception | None = None,
    ):
        self.deployment_id = deployment_id
        if message is None:
            message = "Deployment not found"
            if deployment_id:
                message = f"Deployment not found: {deployment_id}"
        super().__init__(message=message, resource_id=deployment_id, cause=cause)
        self.error_code = "deployment_not_found"


class OperationNotSupportedError(DeploymentError):
    """Raised when a deployment operation is not supported by the current adapter.

    Use this for operations that are valid in the abstract contract but
    are not implemented by the active adapter (e.g. ``redeploy`` or
    ``duplicate`` on a provider that does not support them).
    """

    def __init__(
        self,
        message: str = "This operation is not supported by the current deployment adapter.",
        *,
        cause: Exception | None = None,
    ):
        super().__init__(message, error_code="operation_not_supported", cause=cause)


class DeploymentNotConfiguredError(DeploymentError):
    """Raised when no concrete deployment adapter has been registered.

    The stub :class:`~lfx.services.adapters.deployment.service.DeploymentService` raises
    this for every operation so that callers receive a domain exception rather
    than a bare ``NotImplementedError``.
    """

    def __init__(
        self,
        message: str = (
            "No deployment adapter is registered. Register a concrete adapter to enable deployment operations."
        ),
        *,
        method: str | None = None,
        cause: Exception | None = None,
    ):
        if method is not None:
            message = (
                f"DeploymentService.{method}() requires a concrete deployment adapter. "
                "Register one to enable deployment operations."
            )
        super().__init__(message, error_code="deployment_not_configured", cause=cause)


def http_status_for_deployment_error(exc: DeploymentServiceError) -> int:
    """Return the HTTP status code that best represents a domain exception.

    This is the inverse of :func:`raise_as_deployment_error`: given a
    domain exception instance, it returns the HTTP status code that an API
    layer should use when surfacing the error to a client.

    Order mirrors the except-chain priority in the Langflow route layer:
    more specific exception types are checked before their parents.
    """
    if isinstance(exc, ResourceConflictError):
        return status.HTTP_409_CONFLICT
    if isinstance(exc, InvalidDeploymentOperationError):
        return status.HTTP_400_BAD_REQUEST
    if isinstance(exc, DeploymentSupportError):
        return status.HTTP_400_BAD_REQUEST
    if isinstance(exc, InvalidDeploymentTypeError):
        return status.HTTP_400_BAD_REQUEST
    if isinstance(exc, InvalidContentError):
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    if isinstance(exc, DeploymentNotFoundError):
        return status.HTTP_404_NOT_FOUND
    if isinstance(exc, ResourceNotFoundError):
        return status.HTTP_404_NOT_FOUND
    if isinstance(exc, RateLimitError):
        return status.HTTP_429_TOO_MANY_REQUESTS
    if isinstance(exc, DeploymentTimeoutError):
        return status.HTTP_408_REQUEST_TIMEOUT
    if isinstance(exc, ServiceUnavailableError):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    if isinstance(exc, OperationNotSupportedError):
        return status.HTTP_501_NOT_IMPLEMENTED
    if isinstance(exc, DeploymentNotConfiguredError):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    if isinstance(exc, AuthenticationError):
        return status.HTTP_401_UNAUTHORIZED
    if isinstance(exc, AuthorizationError):
        return status.HTTP_403_FORBIDDEN
    if isinstance(exc, DeploymentError):
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    return status.HTTP_500_INTERNAL_SERVER_ERROR


# Word-boundary regexes avoid false matches in identifiers like "Simple_Agent".
_TOOL_WORD_RE = re.compile(r"\btool\b", re.IGNORECASE)
_CONNECTION_WORD_RE = re.compile(r"\bconnection\b", re.IGNORECASE)
_APP_ID_WORD_RE = re.compile(r"\bapp[_\s-]?id\b", re.IGNORECASE)
_AGENT_WORD_RE = re.compile(r"\bagent\b", re.IGNORECASE)
_TOOL_NAME_RE = re.compile(r"""tool(?:\s+with\s+name|\s+name)?\s*['"](?P<name>[^'"]+)['"]""", re.IGNORECASE)
_AGENT_NAME_RE = re.compile(r"""agent(?:\s+with\s+name|\s+name)?\s*['"](?P<name>[^'"]+)['"]""", re.IGNORECASE)
_APP_ID_QUOTED_RE = re.compile(r"""app[_\s-]?id\s*(?:=|:)?\s*['"](?P<name>[^'"]+)['"]""", re.IGNORECASE)
_APP_ID_UNQUOTED_RE = re.compile(r"""\bapp[_\s-]?id\b\s*(?:=|:)?\s*(?P<name>[A-Za-z0-9_.:-]+)""", re.IGNORECASE)


def _infer_conflict_resource(detail_text: str) -> str | None:
    """Infer conflict resource from provider detail text, when possible."""
    if _TOOL_WORD_RE.search(detail_text):
        return "tool"
    if _CONNECTION_WORD_RE.search(detail_text) or _APP_ID_WORD_RE.search(detail_text):
        return "connection"
    if _AGENT_WORD_RE.search(detail_text):
        return "agent"
    return None


def _infer_conflict_name(detail_text: str, *, resource: str | None) -> str | None:
    """Infer conflict name/identifier from provider detail text."""
    if resource == "tool":
        match = _TOOL_NAME_RE.search(detail_text)
        if match:
            return (match.group("name") or "").strip() or None
        return None
    if resource == "agent":
        match = _AGENT_NAME_RE.search(detail_text)
        if match:
            return (match.group("name") or "").strip() or None
        return None
    if resource == "connection":
        match = _APP_ID_QUOTED_RE.search(detail_text) or _APP_ID_UNQUOTED_RE.search(detail_text)
        if match:
            candidate = (match.group("name") or "").strip()
            return candidate or None
        return None
    return None


def _resolve_conflict_hints(
    detail_text: str,
    *,
    resource: str | None = None,
    resource_name: str | None = None,
) -> tuple[str | None, str | None]:
    normalized_resource = str(resource).strip().lower() if resource is not None else None
    normalized_resource_name = str(resource_name).strip() or None if resource_name is not None else None

    if normalized_resource is None:
        normalized_resource = _infer_conflict_resource(detail_text)
    if normalized_resource_name is None:
        normalized_resource_name = _infer_conflict_name(detail_text, resource=normalized_resource)

    return normalized_resource, normalized_resource_name


# lru+ttl cache?
def raise_as_deployment_error(
    *,
    status_code: int | None,
    detail: str,
    message_prefix: str | None = None,
    resource: str | None = None,
    resource_name: str | None = None,
    cause: Exception | None = None,
) -> NoReturn:
    """Raise domain-specific deployment exceptions based on HTTP-like status/detail.

    When *cause* is ``None`` (the default), implicit exception chaining is
    suppressed (``raise … from None``).  Pass the original exception as
    *cause* to preserve the traceback chain for debugging.  Callers that
    handle security-sensitive errors (e.g. credential verification) should
    set it to None to avoid leaking provider responses through the exception chain.

    For conflict errors, callers should pass ``resource`` and ``resource_name``
    whenever known. Inference from provider detail text is used only as fallback.
    """
    detail_text = str(detail)
    detail_lower = detail_text.lower()
    prefix = str(message_prefix or "").strip()
    message = f"{prefix} error details: {detail_text}" if prefix else detail_text

    if status_code == status.HTTP_401_UNAUTHORIZED:
        raise AuthenticationError(message=message, error_code="authentication_error", cause=cause) from cause
    if status_code == status.HTTP_403_FORBIDDEN:
        raise AuthorizationError(message=message, error_code="authorization_error", cause=cause) from cause
    if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
        raise InvalidContentError(message=message, cause=cause) from cause
    if status_code == status.HTTP_400_BAD_REQUEST:
        raise InvalidDeploymentOperationError(message=message, cause=cause) from cause
    if status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        raise InvalidDeploymentOperationError(message=message, cause=cause) from cause
    if status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
        raise InvalidContentError(message=message, cause=cause) from cause
    if status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE:
        raise InvalidContentError(message=message, cause=cause) from cause
    if status_code == status.HTTP_404_NOT_FOUND:
        raise ResourceNotFoundError(message, cause=cause) from cause
    if status_code == status.HTTP_410_GONE:
        raise ResourceNotFoundError(message, cause=cause) from cause
    if status_code == status.HTTP_409_CONFLICT:
        conflict_resource, conflict_resource_name = _resolve_conflict_hints(
            detail_text,
            resource=resource,
            resource_name=resource_name,
        )
        raise ResourceConflictError(
            message=message,
            resource=conflict_resource,
            resource_name=conflict_resource_name,
            cause=cause,
        ) from cause
    if status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        raise RateLimitError(message=message, cause=cause) from cause
    if status_code in {status.HTTP_408_REQUEST_TIMEOUT, status.HTTP_504_GATEWAY_TIMEOUT}:
        raise DeploymentTimeoutError(message=message, cause=cause) from cause
    if status_code in {status.HTTP_502_BAD_GATEWAY, status.HTTP_503_SERVICE_UNAVAILABLE}:
        raise ServiceUnavailableError(message=message, cause=cause) from cause
    if "not found" in detail_lower:
        raise ResourceNotFoundError(message, cause=cause) from cause
    if "already exists" in detail_lower or "conflict" in detail_lower:
        conflict_resource, conflict_resource_name = _resolve_conflict_hints(
            detail_text,
            resource=resource,
            resource_name=resource_name,
        )
        raise ResourceConflictError(
            message=message,
            resource=conflict_resource,
            resource_name=conflict_resource_name,
            cause=cause,
        ) from cause
    if "unprocessable" in detail_lower:
        raise InvalidContentError(message=message, cause=cause) from cause
    if "too many requests" in detail_lower or "rate limit" in detail_lower:
        raise RateLimitError(message=message, cause=cause) from cause
    if "timed out" in detail_lower or "timeout" in detail_lower:
        raise DeploymentTimeoutError(message=message, cause=cause) from cause
    if (
        "service unavailable" in detail_lower
        or "temporarily unavailable" in detail_lower
        or "bad gateway" in detail_lower
    ):
        raise ServiceUnavailableError(message=message, cause=cause) from cause
    if "unauthorized" in detail_lower or "authentication" in detail_lower:
        raise AuthenticationError(message=message, error_code="authentication_error", cause=cause) from cause
    if "forbidden" in detail_lower or "permission" in detail_lower or "not allowed" in detail_lower:
        raise AuthorizationError(message=message, error_code="authorization_error", cause=cause) from cause
    if "bad request" in detail_lower:
        raise InvalidDeploymentOperationError(message=message, cause=cause) from cause
    if (
        "invalid" in detail_lower
        or "missing" in detail_lower
        or "required" in detail_lower
        or "malformed" in detail_lower
    ):
        raise InvalidContentError(message=message, cause=cause) from cause
    raise DeploymentError(message=message, error_code="deployment_error", cause=cause) from cause


def raise_for_status_and_detail(
    *,
    status_code: int | None,
    detail: str,
    message_prefix: str | None = None,
    resource: str | None = None,
    resource_name: str | None = None,
    cause: Exception | None = None,
) -> NoReturn:
    """Backward-compatible wrapper for ``raise_as_deployment_error``."""
    raise_as_deployment_error(
        status_code=status_code,
        detail=detail,
        message_prefix=message_prefix,
        resource=resource,
        resource_name=resource_name,
        cause=cause,
    )
