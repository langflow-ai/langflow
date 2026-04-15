"""Tests for langflow.services.auth.exceptions module."""

from langflow.services.auth.exceptions import (
    AuthenticationError,
    InactiveUserError,
    InsufficientPermissionsError,
    InvalidCredentialsError,
    InvalidTokenError,
    MissingCredentialsError,
    TokenExpiredError,
)


class TestAuthenticationError:
    def test_message(self):
        exc = AuthenticationError("test error")
        assert exc.message == "test error"
        assert str(exc) == "test error"

    def test_error_code(self):
        exc = AuthenticationError("test", error_code="my_code")
        assert exc.error_code == "my_code"

    def test_no_error_code(self):
        exc = AuthenticationError("test")
        assert exc.error_code is None


class TestInvalidCredentialsError:
    def test_default_message(self):
        exc = InvalidCredentialsError()
        assert exc.message == "Invalid credentials provided"
        assert exc.error_code == "invalid_credentials"

    def test_custom_message(self):
        exc = InvalidCredentialsError("Wrong password")
        assert exc.message == "Wrong password"
        assert exc.error_code == "invalid_credentials"

    def test_is_authentication_error(self):
        assert issubclass(InvalidCredentialsError, AuthenticationError)


class TestMissingCredentialsError:
    def test_default_message(self):
        exc = MissingCredentialsError()
        assert exc.message == "No credentials provided"
        assert exc.error_code == "missing_credentials"

    def test_custom_message(self):
        exc = MissingCredentialsError("Token required")
        assert exc.message == "Token required"


class TestInactiveUserError:
    def test_default_message(self):
        exc = InactiveUserError()
        assert exc.message == "User account is inactive"
        assert exc.error_code == "inactive_user"


class TestInsufficientPermissionsError:
    def test_default_message(self):
        exc = InsufficientPermissionsError()
        assert exc.message == "Insufficient permissions"
        assert exc.error_code == "insufficient_permissions"


class TestTokenExpiredError:
    def test_default_message(self):
        exc = TokenExpiredError()
        assert exc.message == "Authentication token has expired"
        assert exc.error_code == "token_expired"


class TestInvalidTokenError:
    def test_default_message(self):
        exc = InvalidTokenError()
        assert exc.message == "Invalid authentication token"
        assert exc.error_code == "invalid_token"


class TestExceptionHierarchy:
    def test_all_subclass_authentication_error(self):
        subclasses = [
            InvalidCredentialsError,
            MissingCredentialsError,
            InactiveUserError,
            InsufficientPermissionsError,
            TokenExpiredError,
            InvalidTokenError,
        ]
        for cls in subclasses:
            assert issubclass(cls, AuthenticationError), f"{cls.__name__} should be a subclass"
