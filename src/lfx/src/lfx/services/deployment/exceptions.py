"""Framework-agnostic deployment exceptions for LFX deployment service.

Shared exception types so that both minimal (LFX) and full (Langflow) deployment
implementations can raise the same errors.
"""

from __future__ import annotations


class DeploymentError(Exception):
    """Base exception for deployment failures."""

    def __init__(self, message: str, *, error_code: str | None = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class AuthenticationError(DeploymentError):
    """Base exception for authentication failures."""

    def __init__(self, message: str, *, error_code: str | None = None):
        super().__init__(message=message, error_code=error_code)

class DeploymentConflictError(DeploymentError):
    """Raised when a deployment conflict occurs."""

    def __init__(self, message: str = "Deployment conflict occurred"):
        super().__init__(message, error_code="deployment_conflict")

class UnprocessableContentError(DeploymentError):
    """Raised when a deployment request entity is unprocessable."""

    def __init__(self, message: str = "Deployment request entity is unprocessable"):
        super().__init__(message, error_code="unprocessable_content_error")
