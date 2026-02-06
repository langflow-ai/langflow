"""Framework-agnostic authentication exceptions."""

from __future__ import annotations


class AuthenticationError(Exception):
    """Base exception for authentication failures."""

    def __init__(self, message: str, *, error_code: str | None = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class InvalidCredentialsError(AuthenticationError):
    """Raised when provided credentials are invalid."""

    def __init__(self, message: str = "Invalid credentials provided"):
        super().__init__(message, error_code="invalid_credentials")


class MissingCredentialsError(AuthenticationError):
    """Raised when no credentials are provided."""

    def __init__(self, message: str = "No credentials provided"):
        super().__init__(message, error_code="missing_credentials")


class InactiveUserError(AuthenticationError):
    """Raised when user account is inactive."""

    def __init__(self, message: str = "User account is inactive"):
        super().__init__(message, error_code="inactive_user")


class InsufficientPermissionsError(AuthenticationError):
    """Raised when user lacks required permissions."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, error_code="insufficient_permissions")


class TokenExpiredError(AuthenticationError):
    """Raised when authentication token has expired."""

    def __init__(self, message: str = "Authentication token has expired"):
        super().__init__(message, error_code="token_expired")


class InvalidTokenError(AuthenticationError):
    """Raised when token format or signature is invalid."""

    def __init__(self, message: str = "Invalid authentication token"):
        super().__init__(message, error_code="invalid_token")
