"""Unit tests for database URL sanitization to prevent credential exposure.

Security Issue: When DATABASE_URL is misconfigured, sensitive information
(username, password, database name, host) may be exposed in application logs.

This test suite validates that credentials are properly sanitized in error messages.
"""

import pytest
from lfx.utils.util_strings import is_valid_database_url, sanitize_database_url
from pydantic import ValidationError


class TestDatabaseUrlCredentialExposure:
    """Test that database credentials are NOT exposed in error messages."""

    @pytest.mark.parametrize(
        ("invalid_url", "credentials_that_must_not_appear"),
        [
            # PostgreSQL with INVALID port syntax (double colon - the actual bug from screenshot)
            (
                "postgresql+psycopg://myuser:mysecretpassword@127.0.0.1::5432/mydb?sslmode=disable",
                ["myuser", "mysecretpassword"],
            ),
            # Invalid dialect/driver combination
            (
                "invaliddriver://adminuser:secretpass123@localhost:5432/production",
                ["adminuser", "secretpass123"],
            ),
            # Malformed URL with credentials
            (
                "notavaliddb://rootuser:rootpassword@host/badformat",
                ["rootuser", "rootpassword"],
            ),
        ],
    )
    def test_should_not_expose_credentials_when_database_url_is_invalid(
        self,
        invalid_url: str,
        credentials_that_must_not_appear: list[str],
        monkeypatch,
    ):
        """Test that invalid database URL errors do not expose credentials.

        SECURITY: This test validates that when a database URL validation fails,
        our custom error message does NOT contain the username or password.

        Note: Pydantic's ValidationError includes input_value in its metadata,
        which we cannot control. We focus on sanitizing our error message text.
        """
        # Arrange - Settings class reads from environment variables
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", invalid_url)
        monkeypatch.setenv("LANGFLOW_CONFIG_DIR", "/tmp/test_config")

        from lfx.services.settings.base import Settings

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # Get only the first error's message (our controlled text)
        errors = exc_info.value.errors()
        assert len(errors) > 0

        # Extract our custom error message - it's in the 'msg' field
        error_msg = errors[0].get("msg", "")

        # Assert: Credentials MUST NOT appear in OUR error message
        for credential in credentials_that_must_not_appear:
            assert credential not in error_msg, (
                f"SECURITY VULNERABILITY: Credential '{credential}' was exposed!\nError message: {error_msg}"
            )

        # Assert: Masked credentials MUST appear in our message
        assert "***" in error_msg, (
            f"Sanitized credentials (***) not found in error message!\nError message: {error_msg}"
        )


class TestSanitizeDatabaseUrl:
    """Test the sanitize_database_url function."""

    def test_should_mask_username_and_password_in_postgresql_url(self):
        """Test that PostgreSQL URL credentials are masked."""
        # Arrange
        url = "postgresql+psycopg://myuser:mypassword@localhost:5432/mydb"

        # Act
        sanitized = sanitize_database_url(url)

        # Assert
        assert "myuser" not in sanitized
        assert "mypassword" not in sanitized
        assert "***" in sanitized
        assert "localhost:5432" in sanitized
        assert "mydb" in sanitized

    def test_should_mask_credentials_in_mysql_url(self):
        """Test that MySQL URL credentials are masked."""
        # Arrange
        url = "mysql+pymysql://admin:supersecret@db.example.com:3306/app"

        # Act
        sanitized = sanitize_database_url(url)

        # Assert
        assert "admin" not in sanitized
        assert "supersecret" not in sanitized
        assert "***" in sanitized

    def test_should_handle_url_without_credentials(self):
        """Test that URL without credentials is returned unchanged."""
        # Arrange
        url = "sqlite:///./test.db"

        # Act
        sanitized = sanitize_database_url(url)

        # Assert
        assert "sqlite" in sanitized
        assert "test.db" in sanitized

    def test_should_handle_malformed_url_with_regex_fallback(self):
        """Test that malformed URLs are sanitized via regex fallback."""
        # Arrange - malformed URL that SQLAlchemy can't parse, with distinctive credentials
        url = "notvalid://s3cr3tuser:s3cr3tpass@host/db"

        # Act
        sanitized = sanitize_database_url(url)

        # Assert - credentials should be masked
        assert "s3cr3tuser" not in sanitized, f"Credential 's3cr3tuser' was not masked in: {sanitized}"
        assert "s3cr3tpass" not in sanitized, f"Credential 's3cr3tpass' was not masked in: {sanitized}"
        assert "***" in sanitized

    def test_should_mask_password_only_url(self):
        """Test that URL with password but no username is still masked."""
        # Arrange - password-only auth (no username)
        url = "postgresql://:password123@localhost:5432/db"

        # Act
        sanitized = sanitize_database_url(url)

        # Assert
        assert "password123" not in sanitized, f"Password was not masked in: {sanitized}"
        assert "***" in sanitized

    def test_should_handle_empty_url(self):
        """Test that empty URL returns empty string."""
        # Arrange
        url = ""

        # Act
        sanitized = sanitize_database_url(url)

        # Assert
        assert sanitized == ""

    def test_should_handle_none_url(self):
        """Test that None URL returns None."""
        # Arrange
        url = None

        # Act
        sanitized = sanitize_database_url(url)

        # Assert
        assert sanitized is None


class TestDatabaseUrlValidation:
    """Test database URL validation functionality."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            # Valid URLs
            ("sqlite:///./test.db", True),
            ("sqlite+aiosqlite:///./test.db", True),
            ("postgresql://user:pass@localhost:5432/db", True),
            ("postgresql+psycopg://user:pass@localhost:5432/db", True),
            ("mysql+pymysql://user:pass@localhost:3306/db", True),
            # Invalid URLs
            ("not-a-url", False),
            ("http://example.com", False),
            ("ftp://files.example.com", False),
            ("", False),
            # Invalid port syntax (the actual bug)
            ("postgresql+psycopg://user:pass@localhost::5432/db", False),
        ],
    )
    def test_should_validate_database_url_format(self, url: str, *, expected: bool):
        """Test that is_valid_database_url correctly validates URL formats."""
        # Act
        result = is_valid_database_url(url)

        # Assert
        assert result == expected
