"""Security-focused tests for DB2 components."""

import pytest
from lfx.components.ibm.db2_security import (
    create_safe_error_message,
    sanitize_sql_string,
    validate_database_name,
    validate_hostname,
    validate_identifier,
    validate_port,
    validate_sql_query_safety,
)


class TestValidateIdentifier:
    """Test identifier validation (table names, column names, etc.)."""

    def test_valid_identifier(self):
        """Test that valid identifiers pass validation."""
        assert validate_identifier("my_table") == "my_table"
        assert validate_identifier("TABLE123") == "TABLE123"
        assert validate_identifier("_private") == "_private"
        assert validate_identifier("table$name") == "table$name"

    def test_empty_identifier(self):
        """Test that empty identifiers are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_identifier("")

    def test_identifier_too_long(self):
        """Test that identifiers over 128 characters are rejected."""
        long_name = "a" * 129
        with pytest.raises(ValueError, match="cannot exceed 128 characters"):
            validate_identifier(long_name)

    def test_identifier_invalid_characters(self):
        """Test that identifiers with invalid characters are rejected."""
        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("table-name")  # Hyphen not allowed
        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("123table")  # Can't start with number
        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("table name")  # Space not allowed
        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("table;DROP")  # Semicolon not allowed

    def test_identifier_reserved_keyword(self):
        """Test that SQL reserved keywords are rejected."""
        with pytest.raises(ValueError, match="reserved SQL keyword"):
            validate_identifier("SELECT")
        with pytest.raises(ValueError, match="reserved SQL keyword"):
            validate_identifier("DROP")
        with pytest.raises(ValueError, match="reserved SQL keyword"):
            validate_identifier("TABLE")

    def test_sql_injection_attempts(self):
        """Test that SQL injection attempts are blocked."""
        malicious_names = [
            "users; DROP TABLE users; --",
            "users' OR '1'='1",
            "users/**/UNION/**/SELECT",
            "users--",
            "users/*comment*/",
        ]
        for name in malicious_names:
            with pytest.raises(ValueError, match=r"Invalid|reserved SQL keyword"):
                validate_identifier(name)


class TestSanitizeSqlString:
    """Test SQL string sanitization."""

    def test_sanitize_normal_string(self):
        """Test that normal strings pass through unchanged."""
        assert sanitize_sql_string("hello world") == "hello world"
        assert sanitize_sql_string("test123") == "test123"

    def test_sanitize_single_quotes(self):
        """Test that single quotes are properly escaped."""
        assert sanitize_sql_string("it's") == "it''s"
        assert sanitize_sql_string("'quoted'") == "''quoted''"
        assert sanitize_sql_string("multiple'quotes'here") == "multiple''quotes''here"

    def test_sanitize_none(self):
        """Test that None is converted to empty string."""
        assert sanitize_sql_string(None) == ""  # type: ignore[arg-type]

    def test_sanitize_sql_injection_attempts(self):
        """Test that SQL injection attempts are escaped."""
        # These should be escaped, not blocked (blocking happens at validation level)
        assert sanitize_sql_string("'; DROP TABLE users; --") == "''; DROP TABLE users; --"
        assert sanitize_sql_string("' OR '1'='1") == "'' OR ''1''=''1"


class TestValidatePort:
    """Test port number validation."""

    def test_valid_ports(self):
        """Test that valid port numbers pass validation."""
        assert validate_port(50000) == 50000
        assert validate_port(1) == 1
        assert validate_port(65535) == 65535
        assert validate_port(8080) == 8080

    def test_invalid_port_type(self):
        """Test that non-integer ports are rejected."""
        with pytest.raises(TypeError, match="must be an integer"):
            validate_port("50000")  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="must be an integer"):
            validate_port(50000.5)  # type: ignore[arg-type]

    def test_invalid_port_range(self):
        """Test that ports outside valid range are rejected."""
        with pytest.raises(ValueError, match="must be between 1 and 65535"):
            validate_port(0)
        with pytest.raises(ValueError, match="must be between 1 and 65535"):
            validate_port(65536)
        with pytest.raises(ValueError, match="must be between 1 and 65535"):
            validate_port(-1)


class TestValidateHostname:
    """Test hostname validation."""

    def test_valid_hostnames(self):
        """Test that valid hostnames pass validation."""
        assert validate_hostname("localhost") == "localhost"
        assert validate_hostname("127.0.0.1") == "127.0.0.1"
        assert validate_hostname("db.example.com") == "db.example.com"
        assert validate_hostname("db-server-01") == "db-server-01"

    def test_empty_hostname(self):
        """Test that empty hostnames are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_hostname("")

    def test_hostname_sql_injection(self):
        """Test that SQL injection attempts in hostnames are blocked."""
        malicious_hosts = [
            "localhost; DROP TABLE users; --",
            "localhost' OR '1'='1",
            "localhost/**/UNION",
            "localhost--comment",
            "xp_cmdshell",
        ]
        for host in malicious_hosts:
            with pytest.raises(ValueError, match=r"(suspicious pattern|Invalid hostname format)"):
                validate_hostname(host)

    def test_hostname_invalid_format(self):
        """Test that invalid hostname formats are rejected."""
        with pytest.raises(ValueError, match="Invalid hostname format"):
            validate_hostname("host name")  # Space not allowed
        with pytest.raises(ValueError, match="Invalid hostname format"):
            validate_hostname("-hostname")  # Can't start with hyphen
        with pytest.raises(ValueError, match="Invalid hostname format"):
            validate_hostname("hostname-")  # Can't end with hyphen


class TestValidateSqlQuerySafety:
    """Test SQL query safety validation."""

    def test_valid_select_query(self):
        """Test that valid SELECT queries pass validation."""
        validate_sql_query_safety("SELECT * FROM users")
        validate_sql_query_safety("SELECT id, name FROM products WHERE price > 100")

    def test_allowed_operations(self):
        """Test that only allowed operations pass when specified."""
        # Should pass - SELECT is allowed
        validate_sql_query_safety("SELECT * FROM users", allowed_operations={"SELECT"})

        # Should fail - INSERT not allowed
        with pytest.raises(ValueError, match="not allowed"):
            validate_sql_query_safety("INSERT INTO users VALUES (1, 'test')", allowed_operations={"SELECT"})

    def test_empty_query(self):
        """Test that empty queries are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_sql_query_safety("")

    def test_multiple_statements(self):
        """Test that multiple statements are detected and blocked."""
        with pytest.raises(ValueError, match="Multiple statements"):
            validate_sql_query_safety("SELECT * FROM users; DROP TABLE users;")
        with pytest.raises(ValueError, match="Multiple statements"):
            validate_sql_query_safety("SELECT * FROM users; DELETE FROM users;")

    def test_read_only_blocks_chained_insert(self):
        """Test that read-only mode rejects a non-SELECT follow-up statement."""
        with pytest.raises(ValueError, match="Multiple statements"):
            validate_sql_query_safety(
                "SELECT 1; INSERT INTO audit_log VALUES (1)",
                allowed_operations={"SELECT"},
            )

    def test_sql_comments(self):
        """Test that SQL comments are detected."""
        with pytest.raises(ValueError, match="comment detected"):
            validate_sql_query_safety("SELECT * FROM users -- comment")
        with pytest.raises(ValueError, match="comment detected"):
            validate_sql_query_safety("SELECT * FROM users /* block comment */")

    def test_dangerous_procedures(self):
        """Test that dangerous stored procedures are blocked."""
        # EXEC is not in the allowed operations list, so it will fail with "Unable to determine SQL operation type"
        with pytest.raises(ValueError, match="Unable to determine SQL operation type"):
            validate_sql_query_safety("EXEC xp_cmdshell 'dir'")
        with pytest.raises(ValueError, match="Unable to determine SQL operation type"):
            validate_sql_query_safety("EXEC sp_executesql @sql")

    def test_unknown_operation(self):
        """Test that queries with unknown operations are rejected."""
        with pytest.raises(ValueError, match="Unable to determine SQL operation"):
            validate_sql_query_safety("INVALID QUERY")


class TestCreateSafeErrorMessage:
    """Test safe error message creation."""

    def test_db2_connection_error(self):
        """Test that DB2 connection errors are sanitized."""
        error = Exception("SQL30081N A communication error has been detected")
        safe_msg = create_safe_error_message(error, "test context")
        assert "Unable to connect" in safe_msg
        assert "test context" in safe_msg
        assert "SQL30081N" not in safe_msg  # Should not expose error code

    def test_db2_hostname_error(self):
        """Test that hostname resolution errors are sanitized."""
        error = Exception("SQL1336N The remote host was not found")
        safe_msg = create_safe_error_message(error)
        assert "Cannot resolve hostname" in safe_msg
        assert "SQL1336N" not in safe_msg

    def test_db2_auth_error(self):
        """Test that authentication errors are sanitized."""
        error = Exception("SQL30082N Security processing failed")
        safe_msg = create_safe_error_message(error)
        assert "Authentication failed" in safe_msg
        assert "SQL30082N" not in safe_msg

    def test_generic_error(self):
        """Test that generic errors are sanitized."""
        error = Exception("Some internal error with sensitive data")
        safe_msg = create_safe_error_message(error, "during operation")
        assert "Database operation failed" in safe_msg
        assert "during operation" in safe_msg
        assert "sensitive data" not in safe_msg


class TestValidateDatabaseName:
    """Test database name validation."""

    def test_valid_database_names(self):
        """Test that valid database names pass validation."""
        assert validate_database_name("MYDB") == "MYDB"
        assert validate_database_name("test_db") == "test_db"
        assert validate_database_name("DB2INST1") == "DB2INST1"

    def test_invalid_database_names(self):
        """Test that invalid database names are rejected."""
        with pytest.raises(ValueError, match=r"Invalid|reserved SQL keyword"):
            validate_database_name("db; DROP DATABASE;")
        with pytest.raises(ValueError, match="reserved SQL keyword"):
            validate_database_name("SELECT")  # Reserved keyword


# Made with Bob
