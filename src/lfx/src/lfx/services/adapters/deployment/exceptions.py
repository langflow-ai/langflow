"""Framework-agnostic deployment exceptions for LFX deployment service.

Shared exception types for all deployment service implementations,
regardless of adapter.
"""

from __future__ import annotations

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


class DeploymentConflictError(DeploymentError):
    """Raised when a deployment conflict occurs."""

    def __init__(self, message: str = "Deployment conflict occurred", *, cause: Exception | None = None):
        super().__init__(message, error_code="deployment_conflict", cause=cause)


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


# lru+ttl cache?
def raise_for_status_and_detail(
    *,
    status_code: int | None,
    detail: str,
    message_prefix: str | None = None,
) -> NoReturn:
    """Raise domain-specific deployment exceptions based on HTTP-like status/detail."""
    detail_text = str(detail)
    detail_lower = detail_text.lower()
    prefix = str(message_prefix or "").strip()
    message = f"{prefix} error details: {detail_text}" if prefix else detail_text

    if status_code == status.HTTP_401_UNAUTHORIZED:
        raise AuthenticationError(message=message, error_code="authentication_error") from None
    if status_code == status.HTTP_403_FORBIDDEN:
        raise AuthorizationError(message=message, error_code="authorization_error") from None
    if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
        raise InvalidContentError(message=message) from None
    if status_code == status.HTTP_400_BAD_REQUEST:
        raise InvalidDeploymentOperationError(message=message) from None
    if status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        raise InvalidDeploymentOperationError(message=message) from None
    if status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
        raise InvalidContentError(message=message) from None
    if status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE:
        raise InvalidContentError(message=message) from None
    if status_code == status.HTTP_404_NOT_FOUND:
        raise DeploymentNotFoundError(message) from None
    if status_code == status.HTTP_410_GONE:
        raise DeploymentNotFoundError(message) from None
    if status_code == status.HTTP_409_CONFLICT:
        raise DeploymentConflictError(message=message) from None
    if status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        raise RateLimitError(message=message) from None
    if status_code in {status.HTTP_408_REQUEST_TIMEOUT, status.HTTP_504_GATEWAY_TIMEOUT}:
        raise DeploymentTimeoutError(message=message) from None
    if status_code in {status.HTTP_502_BAD_GATEWAY, status.HTTP_503_SERVICE_UNAVAILABLE}:
        raise ServiceUnavailableError(message=message) from None
    if "not found" in detail_lower:
        raise DeploymentNotFoundError(message) from None
    if "already exists" in detail_lower or "conflict" in detail_lower:
        raise DeploymentConflictError(message=message) from None
    if "unprocessable" in detail_lower:
        raise InvalidContentError(message=message) from None
    if "too many requests" in detail_lower or "rate limit" in detail_lower:
        raise RateLimitError(message=message) from None
    if "timed out" in detail_lower or "timeout" in detail_lower:
        raise DeploymentTimeoutError(message=message) from None
    if (
        "service unavailable" in detail_lower
        or "temporarily unavailable" in detail_lower
        or "bad gateway" in detail_lower
    ):
        raise ServiceUnavailableError(message=message) from None
    if "unauthorized" in detail_lower or "authentication" in detail_lower:
        raise AuthenticationError(message=message, error_code="authentication_error") from None
    if "forbidden" in detail_lower or "permission" in detail_lower or "not allowed" in detail_lower:
        raise AuthorizationError(message=message, error_code="authorization_error") from None
    if "bad request" in detail_lower:
        raise InvalidDeploymentOperationError(message=message) from None
    if (
        "invalid" in detail_lower
        or "missing" in detail_lower
        or "required" in detail_lower
        or "malformed" in detail_lower
    ):
        raise InvalidContentError(message=message) from None
    raise DeploymentError(message=message, error_code="deployment_error") from None
