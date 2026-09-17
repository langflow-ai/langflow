"""Unit tests for database URL sanitization to prevent credential exposure.

Security Issue: When DATABASE_URL is misconfigured, sensitive information
(username, password, database name, host) may be exposed in application logs.

This test suite validates that credentials are properly sanitized in error messages.
"""

import pytest
from lfx.utils.util_strings import is_valid_database_url, sanitize_database_url
from pydantic import ValidationError

# Database URLs the settings validator rejects, paired with the credential fragments
# that must never be rendered. Short URLs matter: pydantic truncates long
# ``input_value`` reprs in the middle, which can hide a leak by accident.
REJECTED_DATABASE_URLS = [
    pytest.param(
        "postgres://user:hunter2@db.example:5432/langflow",  # pragma: allowlist secret
        ["hunter2"],  # pragma: allowlist secret
        id="legacy-postgres-scheme",
    ),
    pytest.param(
        "postgresql+nosuchdriver://user:hunter2@db/lf",  # pragma: allowlist secret
        ["hunter2"],  # pragma: allowlist secret
        id="unknown-driver",
    ),
    pytest.param(
        "notadialect://user:hunter2@db/lf",  # pragma: allowlist secret
        ["hunter2"],  # pragma: allowlist secret
        id="unknown-dialect",
    ),
    pytest.param(
        "postgresql://user:hunter2@db:notaport/lf",  # pragma: allowlist secret
        ["hunter2"],  # pragma: allowlist secret
        id="non-numeric-port",
    ),
    pytest.param(
        "user:hunter2@db.example:5432/langflow",  # pragma: allowlist secret
        ["hunter2"],  # pragma: allowlist secret
        id="missing-scheme",
    ),
    pytest.param(
        "postgres://user:hun@ter2@db.example/lf",  # pragma: allowlist secret
        ["hun@ter2", "ter2"],  # pragma: allowlist secret
        id="unescaped-at-in-password",
    ),
    pytest.param(
        "postgres://db.example/lf?user=u&password=hunter2",  # pragma: allowlist secret
        ["hunter2"],  # pragma: allowlist secret
        id="password-in-query",
    ),
    pytest.param(
        "postgresql+psycopg://myuser:mysecretpassword@127.0.0.1::5432/mydb?sslmode=disable",  # pragma: allowlist secret
        ["myuser", "mysecretpassword"],  # pragma: allowlist secret
        id="double-colon-port",
    ),
    pytest.param(
        "invaliddriver://adminuser:secretpass123@localhost:5432/production",  # pragma: allowlist secret
        ["adminuser", "secretpass123"],  # pragma: allowlist secret
        id="invalid-driver",
    ),
    pytest.param(
        "notavaliddb://rootuser:rootpassword@host/badformat",  # pragma: allowlist secret
        ["rootuser", "rootpassword"],  # pragma: allowlist secret
        id="malformed",
    ),
]


def _assert_no_credentials(exc: ValidationError, credentials: list[str]) -> None:
    rendered = {
        "str": str(exc),
        "repr": repr(exc),
        "errors": str(exc.errors(include_input=False, include_url=False)),
    }
    for where, text in rendered.items():
        for credential in credentials:
            assert credential not in text, f"Credential {credential!r} leaked via {where}:\n{text}"


class TestDatabaseUrlCredentialExposure:
    """Test that database credentials are NOT exposed by settings validation errors."""

    @pytest.mark.parametrize(("invalid_url", "credentials_that_must_not_appear"), REJECTED_DATABASE_URLS)
    def test_should_not_expose_credentials_when_database_url_is_invalid(
        self,
        invalid_url: str,
        credentials_that_must_not_appear: list[str],
        monkeypatch,
        tmp_path,
    ):
        """A rejected database URL must not leak credentials through the ValidationError.

        Pydantic renders ``input_value=<raw input>`` in ``str(exc)``/``repr(exc)`` unless the
        model hides inputs, so masking only the message text is not enough.
        """
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", invalid_url)
        monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))

        from lfx.services.settings.base import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        _assert_no_credentials(exc_info.value, credentials_that_must_not_appear)
        assert "input_value" not in str(exc_info.value)

        # The message stays actionable: it names the problem and shows the masked URL.
        error_msg = exc_info.value.errors()[0]["msg"]
        assert "Invalid database_url provided" in error_msg
        assert "***" in error_msg

    @pytest.mark.parametrize(("invalid_url", "credentials_that_must_not_appear"), REJECTED_DATABASE_URLS)
    def test_should_not_expose_credentials_when_database_url_is_assigned(
        self,
        invalid_url: str,
        credentials_that_must_not_appear: list[str],
        monkeypatch,
        tmp_path,
    ):
        """``Settings`` validates on assignment, so the same guarantee must hold for setattr."""
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{tmp_path / 'langflow.db'}")
        monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))

        from lfx.services.settings.base import Settings

        settings = Settings()
        with pytest.raises(ValidationError) as exc_info:
            settings.database_url = invalid_url

        _assert_no_credentials(exc_info.value, credentials_that_must_not_appear)

    def test_should_keep_masked_host_and_database_in_message(self, monkeypatch, tmp_path):
        """Hiding the input must not strip the context an operator needs to fix the URL."""
        invalid_url = "postgres://user:hunter2@db.example:5432/langflow"  # pragma: allowlist secret
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", invalid_url)
        monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))

        from lfx.services.settings.base import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        message = str(exc_info.value)
        assert "database_url" in message
        assert "postgres://" in message
        assert "db.example:5432/langflow" in message


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

    def test_should_mask_credentials_when_scheme_is_missing(self):
        """The unparseable-URL fallback must not require ``://`` to find credentials."""
        sanitized = sanitize_database_url("user:hunter2@db.example:5432/langflow")  # pragma: allowlist secret

        assert "hunter2" not in sanitized  # pragma: allowlist secret
        assert sanitized == "***:***@db.example:5432/langflow"

    @pytest.mark.parametrize(
        "url",
        [
            # SQLAlchemy parses this, but splits the password at the first "@".
            "postgres://user:hun@ter2@db.example/lf",  # pragma: allowlist secret
            # SQLAlchemy cannot parse this (non-numeric port), so the fallback runs.
            "postgresql://user:hun@ter2@db.example:notaport/lf",  # pragma: allowlist secret
        ],
    )
    def test_should_mask_whole_password_containing_unescaped_at(self, url: str):
        """Passwords with an unescaped ``@`` must be masked up to the last ``@``."""
        sanitized = sanitize_database_url(url)

        assert "ter2" not in sanitized, f"Password tail leaked in: {sanitized}"  # pragma: allowlist secret
        assert "user" not in sanitized
        assert "***:***@db.example" in sanitized

    @pytest.mark.parametrize(
        "url",
        [
            "postgres://db.example/lf?user=u&password=hunter2&sslmode=disable",  # pragma: allowlist secret
            "notadialect://db.example:bad/lf?sslmode=disable&sslpassword=hunter2",  # pragma: allowlist secret
        ],
    )
    def test_should_mask_sensitive_query_parameters(self, url: str):
        """libpq-style ``password``/``sslpassword`` query parameters are credentials too."""
        sanitized = sanitize_database_url(url)

        assert "hunter2" not in sanitized  # pragma: allowlist secret
        assert "sslmode=disable" in sanitized

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
