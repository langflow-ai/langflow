"""Lightweight validation and safe error helpers for IBM Db2 components."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
_HOSTNAME_PATTERN = re.compile(r"^[A-Za-z0-9.-]{1,253}$")


def _require_string(value: object, field_name: str) -> str:
    """Return a stripped string or raise TypeError."""
    if not isinstance(value, str):
        msg = f"Invalid {field_name}: must be a string"
        raise TypeError(msg)

    cleaned = value.strip()
    if not cleaned:
        msg = f"Invalid {field_name}: cannot be empty"
        raise ValueError(msg)
    return cleaned


# Maximum length for Db2 database names
_MAX_DB_NAME_LENGTH = 128


def validate_database_name(value: object) -> str:
    """Validate a Db2 database name."""
    database_name = _require_string(value, "database name")
    if len(database_name) > _MAX_DB_NAME_LENGTH:
        msg = "Invalid database name: exceeds maximum length"
        raise ValueError(msg)
    if any(char in database_name for char in ('"', "'", ";", "\\", "\n", "\r", "\t")):
        msg = "Invalid database name: contains unsafe characters"
        raise ValueError(msg)
    return database_name


def validate_hostname(value: object) -> str:
    """Validate a hostname or IP-like address."""
    hostname = _require_string(value, "hostname")
    if any(char in hostname for char in ('"', "'", ";", "\\", "/", "?", "#", "\n", "\r", "\t", " ")):
        msg = "Invalid hostname: contains unsafe characters"
        raise ValueError(msg)
    if not _HOSTNAME_PATTERN.fullmatch(hostname):
        msg = "Invalid hostname: contains unsupported characters"
        raise ValueError(msg)
    if ".." in hostname or hostname.startswith((".", "-")) or hostname.endswith("."):
        msg = "Invalid hostname: malformed hostname"
        raise ValueError(msg)
    return hostname


# Valid TCP port range
_MIN_PORT = 1
_MAX_PORT = 65535


def validate_port(value: object) -> int:
    """Validate a TCP port number."""
    if isinstance(value, bool) or not isinstance(value, int):
        msg = "Invalid port: must be an integer"
        raise TypeError(msg)
    if value < _MIN_PORT or value > _MAX_PORT:
        msg = f"Invalid port: must be between {_MIN_PORT} and {_MAX_PORT}"
        raise ValueError(msg)
    return value


def validate_identifier(value: object, field_name: str = "identifier") -> str:
    """Validate a SQL identifier used for table names."""
    identifier = _require_string(value, field_name)
    if not _IDENTIFIER_PATTERN.fullmatch(identifier):
        msg = f"Invalid {field_name}: use letters, numbers, and underscores only, starting with a letter"
        raise ValueError(msg)
    return identifier


def get_quoted_identifier(identifier: str) -> str:
    """Return a properly quoted SQL identifier for Db2.

    Args:
        identifier: The identifier to quote (already validated)

    Returns:
        The quoted identifier safe for SQL queries
    """
    # Db2 uses double quotes for identifiers
    # Escape any existing double quotes by doubling them
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def sanitize_sql_string(value: str) -> str:
    """Sanitize a string value for use in SQL queries.

    Args:
        value: The string value to sanitize

    Returns:
        The sanitized string with dangerous characters escaped
    """
    # Escape single quotes by doubling them (SQL standard)
    return value.replace("'", "''")


def create_safe_error_message(error: Exception, context: str | None = None) -> str:
    """Create a sanitized error message without exposing connection details."""
    error_text = str(error).strip() or "Unknown error"
    redacted_text = error_text

    sensitive_patterns = [
        r"PWD=[^; ]+",
        r"PASSWORD=[^; ]+",
        r"UID=[^; ]+",
        r"USER(ID)?=[^; ]+",
        r"HOSTNAME=[^; ]+",
        r"DATABASE=[^; ]+",
        r"PORT=[^; ]+",
    ]
    for pattern in sensitive_patterns:
        redacted_text = re.sub(pattern, "[REDACTED]", redacted_text, flags=re.IGNORECASE)

    prefix = "DB2 operation failed"
    if context:
        prefix = f"{prefix} {context}"

    return f"{prefix}: {redacted_text}"


def validate_ssl_certificate_path(cert_path: str | None) -> tuple[str | None, str | None]:
    """Validate and resolve SSL certificate path.

    Args:
        cert_path: Path to certificate file (local path or URL), or None

    Returns:
        Tuple of (resolved_path, error_message)
        - If valid: (resolved_path, None)
        - If invalid: (None, error_message)
        - If None/empty: (None, None) - indicates use system defaults

    Raises:
        ValueError: If certificate path is invalid or file doesn't exist
    """
    if not cert_path or not cert_path.strip():
        # Empty path means use system defaults
        return None, None

    cert_path = cert_path.strip()

    # Check if it's a URL
    parsed = urlparse(cert_path)
    if parsed.scheme in ("http", "https"):
        # URL-based certificate - will be downloaded later
        return cert_path, None

    # Local file path - validate it exists and is readable
    try:
        # Resolve path (handles relative paths, ~, etc.)
        resolved_path = Path(cert_path).expanduser().resolve()

        # Check if file exists
        if not resolved_path.exists():
            return None, f"Certificate file not found: {cert_path}"

        # Check if it's a file (not a directory)
        if not resolved_path.is_file():
            return None, f"Certificate path is not a file: {cert_path}"

        # Check if file is readable
        if not os.access(resolved_path, os.R_OK):
            return None, f"Certificate file is not readable: {cert_path}"

        # Validate file extension
        valid_extensions = {".crt", ".pem", ".cer", ".cert"}
        if resolved_path.suffix.lower() not in valid_extensions:
            return (
                None,
                f"Invalid certificate file extension: {resolved_path.suffix}. "
                f"Expected one of: {', '.join(valid_extensions)}",
            )

        return str(resolved_path), None

    except (OSError, ValueError) as e:
        return None, f"Error validating certificate path: {e}"


def download_certificate(url: str) -> tuple[str | None, str | None]:
    """Download SSL certificate from URL to temporary file.

    Args:
        url: URL to download certificate from

    Returns:
        Tuple of (temp_file_path, error_message)
        - If successful: (temp_file_path, None)
        - If failed: (None, error_message)
    """
    try:
        import urllib.error
        import urllib.request

        # Create temporary file with appropriate extension
        temp_fd, temp_path = tempfile.mkstemp(suffix=".crt", prefix="db2_ssl_")

        try:
            # Download certificate
            with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
                cert_data = response.read()

            # Write to temporary file
            with os.fdopen(temp_fd, "wb") as f:
                f.write(cert_data)

        except (OSError, ValueError, urllib.error.URLError) as download_error:
            # Clean up temp file on error
            try:
                os.close(temp_fd)
                Path(temp_path).unlink(missing_ok=True)
            except OSError:
                # Ignore cleanup errors
                pass
            return None, f"Failed to download certificate from {url}: {download_error}"
        else:
            return temp_path, None

    except (OSError, ValueError) as e:
        return None, f"Error setting up certificate download: {e}"


def validate_and_prepare_ssl_certificate(cert_path: str | None) -> tuple[str | None, bool, str | None]:
    """Validate and prepare SSL certificate for use.

    Args:
        cert_path: Path to certificate file (local path or URL), or None

    Returns:
        Tuple of (resolved_path, is_temp_file, error_message)
        - resolved_path: Path to use for SSL connection (None means use system defaults)
        - is_temp_file: True if the file is temporary and should be cleaned up
        - error_message: Error message if validation failed, None otherwise
    """
    if not cert_path or not cert_path.strip():
        # No certificate provided - use system defaults
        return None, False, None

    # First validate the path/URL
    validated_path, error = validate_ssl_certificate_path(cert_path)
    if error:
        return None, False, error

    # Check if it's a URL that needs downloading
    parsed = urlparse(cert_path)
    if parsed.scheme in ("http", "https"):
        # Download certificate to temporary file
        temp_path, download_error = download_certificate(cert_path)
        if download_error:
            return None, False, download_error
        return temp_path, True, None

    # Local file path - already validated
    return validated_path, False, None


# Made with Bob
