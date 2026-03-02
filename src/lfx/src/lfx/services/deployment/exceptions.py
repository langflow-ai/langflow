"""Deployment exceptions for LFX deployment service."""

from __future__ import annotations


class DeploymentError(Exception):
    """Base exception for deployment failures."""

    def __init__(self, message: str, *, error_code: str | None = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class DeploymentNotFoundError(DeploymentError):
    """Raised when a deployment is not found."""

    def __init__(self, message: str = "Deployment not found"):
        super().__init__(message, error_code="deployment_not_found")


class DeploymentConflictError(DeploymentError):
    """Raised when a deployment conflict occurs."""

    def __init__(self, message: str = "Deployment conflict occurred"):
        super().__init__(message, error_code="deployment_conflict")


class InvalidContentError(DeploymentError):
    """Raised when a deployment request entity is unprocessable."""

    def __init__(self, message: str = "Deployment request entity is unprocessable"):
        super().__init__(message, error_code="unprocessable_content_error")


class InvalidDeploymentOperationError(DeploymentError):
    """Raised when a deployment operation is invalid for current adapter semantics."""

    def __init__(self, message: str = "Invalid deployment operation"):
        super().__init__(message, error_code="invalid_deployment_operation")


class InvalidDeploymentTypeError(DeploymentError):
    """Raised when an invalid deployment type is provided."""

    def __init__(self, message: str = "Invalid deployment type"):
        super().__init__(message, error_code="invalid_deployment_type")


class DeploymentSupportError(DeploymentError):
    """Raised when a deployment type is unsupported."""

    def __init__(self, message: str = "Deployment type is unsupported"):
        super().__init__(message, error_code="unsupported_deployment_type")
