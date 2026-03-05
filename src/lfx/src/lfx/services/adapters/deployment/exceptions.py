"""Framework-agnostic deployment exceptions for LFX deployment service.

Shared exception types for all deployment service implementations,
regardless of adapter.
"""

from __future__ import annotations


class DeploymentServiceError(Exception):
    """Root exception for all deployment service failures.

    Both operational errors (:class:`DeploymentError`) and authentication
    errors (:class:`AuthenticationError`) inherit from this class.
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


class DeploymentNotFoundError(DeploymentError):
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
        super().__init__(message, error_code="deployment_not_found", cause=cause)


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
