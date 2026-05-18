"""Security utilities for DB2 components."""

import re

# DB2 reserved keywords that should not be used as identifiers
DB2_RESERVED_KEYWORDS = {
    "ADD",
    "ALL",
    "ALLOCATE",
    "ALTER",
    "AND",
    "ANY",
    "ARE",
    "AS",
    "ASC",
    "ASSERTION",
    "AT",
    "AUTHORIZATION",
    "AVG",
    "BEGIN",
    "BETWEEN",
    "BIT",
    "BOOLEAN",
    "BOTH",
    "BY",
    "CALL",
    "CASCADE",
    "CASCADED",
    "CASE",
    "CAST",
    "CHAR",
    "CHARACTER",
    "CHECK",
    "CLOSE",
    "COLLATE",
    "COLUMN",
    "COMMIT",
    "CONNECT",
    "CONNECTION",
    "CONSTRAINT",
    "CONSTRAINTS",
    "CONTINUE",
    "CORRESPONDING",
    "COUNT",
    "CREATE",
    "CROSS",
    "CURRENT",
    "CURSOR",
    "DATE",
    "DAY",
    "DEALLOCATE",
    "DEC",
    "DECIMAL",
    "DECLARE",
    "DEFAULT",
    "DELETE",
    "DESC",
    "DESCRIBE",
    "DESCRIPTOR",
    "DIAGNOSTICS",
    "DISCONNECT",
    "DISTINCT",
    "DOMAIN",
    "DOUBLE",
    "DROP",
    "ELSE",
    "END",
    "ESCAPE",
    "EXCEPT",
    "EXCEPTION",
    "EXEC",
    "EXECUTE",
    "EXISTS",
    "EXTERNAL",
    "EXTRACT",
    "FALSE",
    "FETCH",
    "FIRST",
    "FLOAT",
    "FOR",
    "FOREIGN",
    "FOUND",
    "FROM",
    "FULL",
    "GET",
    "GLOBAL",
    "GO",
    "GOTO",
    "GRANT",
    "GROUP",
    "HAVING",
    "HOUR",
    "IDENTITY",
    "IMMEDIATE",
    "IN",
    "INDICATOR",
    "INITIALLY",
    "INNER",
    "INPUT",
    "INSENSITIVE",
    "INSERT",
    "INT",
    "INTEGER",
    "INTERSECT",
    "INTERVAL",
    "INTO",
    "IS",
    "ISOLATION",
    "JOIN",
    "KEY",
    "LANGUAGE",
    "LAST",
    "LEADING",
    "LEFT",
    "LEVEL",
    "LIKE",
    "LOCAL",
    "LOWER",
    "MATCH",
    "MAX",
    "MIN",
    "MINUTE",
    "MODULE",
    "MONTH",
    "NAMES",
    "NATIONAL",
    "NATURAL",
    "NCHAR",
    "NEXT",
    "NO",
    "NOT",
    "NULL",
    "NULLIF",
    "NUMERIC",
    "OCTET_LENGTH",
    "OF",
    "ON",
    "ONLY",
    "OPEN",
    "OPTION",
    "OR",
    "ORDER",
    "OUTER",
    "OUTPUT",
    "OVERLAPS",
    "PAD",
    "PARTIAL",
    "POSITION",
    "PRECISION",
    "PREPARE",
    "PRESERVE",
    "PRIMARY",
    "PRIOR",
    "PRIVILEGES",
    "PROCEDURE",
    "PUBLIC",
    "READ",
    "REAL",
    "REFERENCES",
    "RELATIVE",
    "RESTRICT",
    "REVOKE",
    "RIGHT",
    "ROLLBACK",
    "ROWS",
    "SCHEMA",
    "SCROLL",
    "SECOND",
    "SECTION",
    "SELECT",
    "SESSION",
    "SET",
    "SIZE",
    "SMALLINT",
    "SOME",
    "SPACE",
    "SQL",
    "SQLCODE",
    "SQLERROR",
    "SQLSTATE",
    "SUBSTRING",
    "SUM",
    "SYSTEM_USER",
    "TABLE",
    "TEMPORARY",
    "THEN",
    "TIME",
    "TIMESTAMP",
    "TIMEZONE_HOUR",
    "TIMEZONE_MINUTE",
    "TO",
    "TRAILING",
    "TRANSACTION",
    "TRANSLATE",
    "TRANSLATION",
    "TRIM",
    "TRUE",
    "UNION",
    "UNIQUE",
    "UNKNOWN",
    "UPDATE",
    "UPPER",
    "USAGE",
    "USER",
    "USING",
    "VALUE",
    "VALUES",
    "VARCHAR",
    "VARYING",
    "VIEW",
    "WHEN",
    "WHENEVER",
    "WHERE",
    "WITH",
    "WORK",
    "WRITE",
    "YEAR",
    "ZONE",
}


def validate_identifier(identifier: str, identifier_type: str = "identifier") -> str:
    """Validate and sanitize a DB2 identifier (table name, column name, etc.).

    Args:
        identifier: The identifier to validate
        identifier_type: Type of identifier for error messages (e.g., "table name", "column name")

    Returns:
        The validated identifier

    Raises:
        ValueError: If the identifier is invalid
    """
    if not identifier:
        msg = f"{identifier_type} cannot be empty"
        raise ValueError(msg)

    # Remove any whitespace
    identifier = identifier.strip()

    # Check length (DB2 max identifier length is 128 characters)
    max_identifier_length = 128
    if len(identifier) > max_identifier_length:
        msg = f"{identifier_type} cannot exceed {max_identifier_length} characters"
        raise ValueError(msg)

    # Check for valid characters: alphanumeric, underscore, and dollar sign
    # Must start with letter or underscore
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_$]*$", identifier):
        msg = (
            f"Invalid {identifier_type}: '{identifier}'. "
            f"Must start with a letter or underscore and contain only "
            f"alphanumeric characters, underscores, or dollar signs."
        )
        raise ValueError(msg)

    # Check if it's a reserved keyword
    if identifier.upper() in DB2_RESERVED_KEYWORDS:
        msg = (
            f"Invalid {identifier_type}: '{identifier}' is a reserved SQL keyword. "
            f"Please use a different name or quote it."
        )
        raise ValueError(msg)

    return identifier


def sanitize_sql_string(value: str) -> str:
    """Sanitize a string value for use in SQL queries.

    Escapes single quotes by doubling them (SQL standard).

    Args:
        value: The string to sanitize

    Returns:
        The sanitized string
    """
    if value is None:
        return ""
    return str(value).replace("'", "''")


def validate_port(port: int) -> int:
    """Validate a port number.

    Args:
        port: The port number to validate

    Returns:
        The validated port number

    Raises:
        ValueError: If the port is invalid
    """
    # Port range constants
    min_port = 1
    max_port = 65535

    if not isinstance(port, int):
        msg = f"Port must be an integer, got {type(port).__name__}"
        raise TypeError(msg)

    if port < min_port or port > max_port:
        msg = f"Port must be between {min_port} and {max_port}, got {port}"
        raise ValueError(msg)

    return port


def validate_hostname(hostname: str) -> str:
    """Validate a hostname or IP address.

    Args:
        hostname: The hostname to validate

    Returns:
        The validated hostname

    Raises:
        ValueError: If the hostname is invalid
    """
    if not hostname:
        msg = "Hostname cannot be empty"
        raise ValueError(msg)

    hostname = hostname.strip()

    # Basic hostname validation (alphanumeric, dots, hyphens)
    # This regex validates proper hostname format and prevents SQL metacharacters
    if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$", hostname):
        msg = f"Invalid hostname format: '{hostname}'"
        raise ValueError(msg)

    # Check for SQL metacharacters and comment patterns only
    # (not keywords, as they can appear in legitimate hostnames)
    sql_metacharacters = [";", "--", "/*", "*/"]
    for pattern in sql_metacharacters:
        if pattern in hostname:
            msg = f"Invalid hostname: contains suspicious pattern '{pattern}'"
            raise ValueError(msg)

    return hostname


def validate_database_name(database: str) -> str:
    """Validate a database name.

    Args:
        database: The database name to validate

    Returns:
        The validated database name

    Raises:
        ValueError: If the database name is invalid
    """
    return validate_identifier(database, "database name")


def create_safe_error_message(error: Exception, context: str = "") -> str:
    """Create a safe error message that doesn't expose sensitive information.

    Args:
        error: The original exception
        context: Additional context about where the error occurred

    Returns:
        A safe error message for users
    """
    error_str = str(error)

    # Check for specific DB2 error codes
    if "SQL30081N" in error_str:
        return f"Connection failed: Unable to connect to the database server. {context}"
    if "SQL1336N" in error_str:
        return f"Connection failed: Cannot resolve hostname. {context}"
    if "SQL30082N" in error_str:
        return "Authentication failed: Invalid username or password."
    if "SQL0204N" in error_str:
        return f"Table or view not found. {context}"
    if "SQL0206N" in error_str:
        return f"Column not found. {context}"
    if "SQL0407N" in error_str:
        return f"Required value is missing. {context}"
    if "SQL0803N" in error_str:
        return f"Duplicate key violation. {context}"

    # Generic error message
    return f"Database operation failed. {context}"


def validate_sql_query_safety(query: str, allowed_operations: set[str] | None = None) -> None:
    """Validate that a SQL query is safe to execute.

    This is a basic validation and should be used in conjunction with other security measures.

    Args:
        query: The SQL query to validate
        allowed_operations: Set of allowed SQL operations (e.g., {'SELECT', 'INSERT'})

    Raises:
        ValueError: If the query appears to be unsafe
    """
    if not query:
        msg = "SQL query cannot be empty"
        raise ValueError(msg)

    query_upper = query.strip().upper()

    # Detect the operation type
    operation = None
    for op in ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TRUNCATE"]:
        if query_upper.startswith(op):
            operation = op
            break

    if not operation:
        msg = "Unable to determine SQL operation type"
        raise ValueError(msg)

    # Check if operation is allowed
    if allowed_operations and operation not in allowed_operations:
        msg = f"SQL operation '{operation}' is not allowed. Allowed operations: {allowed_operations}"
        raise ValueError(msg)

    # Reject chained statements (e.g. SELECT 1; INSERT ...) not only DROP/DELETE/TRUNCATE
    if ";" in query:
        trailing_parts = [part.strip() for part in query.split(";")[1:] if part.strip()]
        if trailing_parts:
            if allowed_operations is not None:
                for part in trailing_parts:
                    part_upper = part.upper()
                    sql_ops = [
                        "SELECT",
                        "INSERT",
                        "UPDATE",
                        "DELETE",
                        "CREATE",
                        "DROP",
                        "ALTER",
                        "TRUNCATE",
                    ]
                    follow_up_op = next(
                        (op for op in sql_ops if part_upper.startswith(op)),
                        None,
                    )
                    if follow_up_op is None:
                        msg = "Potentially unsafe SQL query: Multiple statements detected"
                        raise ValueError(msg)
                    if follow_up_op not in allowed_operations:
                        msg = (
                            f"Potentially unsafe SQL query: Multiple statements detected "
                            f"({follow_up_op} is not allowed)"
                        )
                        raise ValueError(msg)
            else:
                msg = "Potentially unsafe SQL query: Multiple statements detected"
                raise ValueError(msg)

    # Check for dangerous patterns
    dangerous_patterns = [
        (r";\s*DROP", "Multiple statements with DROP detected"),
        (r";\s*DELETE", "Multiple statements with DELETE detected"),
        (r";\s*TRUNCATE", "Multiple statements with TRUNCATE detected"),
        (r";\s*INSERT", "Multiple statements with INSERT detected"),
        (r";\s*UPDATE", "Multiple statements with UPDATE detected"),
        (r";\s*CREATE", "Multiple statements with CREATE detected"),
        (r";\s*ALTER", "Multiple statements with ALTER detected"),
        (r"--", "SQL comment detected"),
        (r"/\*", "SQL block comment detected"),
        (r"xp_cmdshell", "Dangerous stored procedure detected"),
        (r"EXEC\s+", "EXEC statement detected"),
        (r"EXECUTE\s+", "EXECUTE statement detected"),
    ]

    for pattern, message in dangerous_patterns:
        if re.search(pattern, query_upper):
            msg = f"Potentially unsafe SQL query: {message}"
            raise ValueError(msg)


def get_quoted_identifier(identifier: str) -> str:
    """Get a properly quoted identifier for use in SQL queries.

    Args:
        identifier: The identifier to quote

    Returns:
        The quoted identifier
    """
    # Validate first
    validate_identifier(identifier)

    # Quote the identifier to prevent SQL injection
    # DB2 uses double quotes for identifiers
    return f'"{identifier}"'


# Made with Bob
