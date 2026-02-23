"""Framework-agnostic deployment router exceptions for LFX."""

from __future__ import annotations


class DeploymentRouterError(Exception):
    """Base exception for deployment router failures."""

    def __init__(self, message: str, *, error_code: str | None = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class DeploymentAccountNotFoundError(DeploymentRouterError):
    """Raised when a deployment account is missing or inaccessible."""

    def __init__(self, message: str = "Deployment provider account not found"):
        super().__init__(message=message, error_code="deployment_account_not_found")


class DeploymentAdapterNotRegisteredError(DeploymentRouterError):
    """Raised when no adapter exists for a resolved account provider key."""

    def __init__(self, message: str = "No deployment adapter is registered for this account"):
        super().__init__(message=message, error_code="deployment_adapter_not_registered")
