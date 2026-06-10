"""Unit tests for lightweight DB2 security helpers."""

import pytest
from lfx_ibm.components.ibm.db2_security import (
    create_safe_error_message,
    validate_database_name,
    validate_hostname,
    validate_identifier,
    validate_port,
)


def test_validate_database_name_accepts_valid_name():
    """Database names with safe characters should pass validation."""
    assert validate_database_name("TESTDB") == "TESTDB"


def test_validate_database_name_rejects_unsafe_characters():
    """Unsafe characters should be rejected from database names."""
    with pytest.raises(ValueError, match="unsafe characters"):
        validate_database_name("TESTDB; DROP TABLE users;")


def test_validate_hostname_accepts_valid_hostname():
    """Standard hostnames should pass validation."""
    assert validate_hostname("localhost") == "localhost"


def test_validate_hostname_rejects_unsafe_characters():
    """Unsafe characters should be rejected from hostnames."""
    with pytest.raises(ValueError, match="unsafe characters"):
        validate_hostname("localhost;rm -rf /")


def test_validate_port_accepts_valid_port():
    """Valid TCP ports should pass validation."""
    assert validate_port(50000) == 50000


def test_validate_port_rejects_out_of_range_value():
    """Out-of-range ports should fail validation."""
    with pytest.raises(ValueError, match="between 1 and 65535"):
        validate_port(70000)


def test_validate_identifier_accepts_table_name():
    """Safe SQL identifiers should pass validation."""
    assert validate_identifier("LANGFLOW_VECTORS", "table name") == "LANGFLOW_VECTORS"


def test_validate_identifier_rejects_invalid_identifier():
    """Unsafe table names should fail validation."""
    with pytest.raises(ValueError, match="table name"):
        validate_identifier("invalid-table", "table name")


def test_create_safe_error_message_redacts_connection_details():
    """Sensitive connection string values should be redacted."""
    error = RuntimeError("DATABASE=TESTDB;HOSTNAME=localhost;PORT=50000;UID=db2inst1;PWD=secret")
    message = create_safe_error_message(error, "while connecting to database")

    assert "TESTDB" not in message
    assert "localhost" not in message
    assert "50000" not in message
    assert "db2inst1" not in message
    assert "secret" not in message
    assert "[REDACTED]" in message
    assert "while connecting to database" in message


# Made with Bob
