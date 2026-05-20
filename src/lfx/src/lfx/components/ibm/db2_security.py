"""Lightweight validation and safe error helpers for IBM Db2 components."""

from __future__ import annotations

import re

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


# Made with Bob
