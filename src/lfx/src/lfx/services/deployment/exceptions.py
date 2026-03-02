"""Framework-agnostic deployment exceptions for LFX deployment service.

Shared exception types so that both minimal (LFX) and full (Langflow) deployment
implementations can raise the same errors.
"""

from __future__ import annotations


class DeploymentError(Exception):
    """Base exception for deployment failures."""

    def __init__(self, message: str, *, error_code: str | None = None, cause: Exception | None = None):
        self.message = message
        self.error_code = error_code
        self.cause = cause
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause


class AuthenticationError(DeploymentError):
    """Base exception for authentication failures.

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
        if message is None:
            message = "Deployment not found"
            if deployment_id:
                message = f"Deployment not found: {deployment_id}"
        super().__init__(message, error_code="deployment_not_found", cause=cause)
