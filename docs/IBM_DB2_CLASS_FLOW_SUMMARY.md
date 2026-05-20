# IBM DB2 Integration - Class Flow Summary

## Overview

The IBM DB2 integration for Langflow provides two primary components: **DB2 Vector Store** for semantic search and RAG applications, and **DB2 SQL** for secure query execution. Both components share a common security layer that ensures enterprise-grade protection against SQL injection and unauthorized access.

---

## 1. DB2 Vector Store Component - Class Flow

**File Structure:**
- `src/lfx/src/lfx/components/ibm/db2_vector.py` - High-level Langflow component
- `src/lfx/src/lfx/components/ibm/db2vs.py` - Core vector store implementation
- `src/lfx/src/lfx/components/ibm/db2_security.py` - Shared security validation layer

**Class Flow Description:**

The DB2 Vector Store component follows a three-tier architecture. At the top level, the **`DB2VectorStoreComponent`** class (inheriting from `LCVectorStoreComponent`) serves as the Langflow-facing interface, handling user inputs like database credentials, table names, embedding models, and search parameters. When a user initiates data ingestion, the component first parses incoming data from multiple formats (DataFrame, CSV, JSON, plain text) and extracts both text content and metadata fields (brand, category, price, tenant_id). It then passes this data to the **`DB2VS`** core class, which manages the actual vector operations.

The **`DB2VS`** class is the heart of the vector store implementation. Upon initialization, it validates the embedding dimension by generating a test embedding, checks if the target table exists in DB2, and automatically creates the table with proper schema (ID, TEXT, METADATA, EMBEDDING columns) if needed. For data insertion, it receives documents from the component layer, generates embeddings using the provided embedding function, validates each embedding's dimension to ensure consistency, and then constructs parameterized SQL INSERT statements. Before executing any database operation, all identifiers (table names, column names) and string values pass through the **`db2_security`** module's validation functions (`validate_identifier()`, `sanitize_sql_string()`), which block SQL injection attempts, reserved keywords, and malicious patterns. The class supports multiple distance metrics (COSINE, EUCLIDEAN, DOT_PRODUCT) for similarity calculations and implements both standard k-NN similarity search and Maximum Marginal Relevance (MMR) search for diversity-aware results. All database queries use parameterized statements with proper escaping, and errors are sanitized through `create_safe_error_message()` to prevent credential leakage in logs.

---

## 2. DB2 SQL Component - Class Flow

**File Structure:**
- `src/lfx/src/lfx/components/ibm/db2_sql.py` - SQL execution component
- `src/lfx/src/lfx/components/ibm/db2_security.py` - Shared security validation layer

**Class Flow Description:**

The DB2 SQL component provides secure, controlled SQL query execution through the **`DB2SQLComponent`** class. This component accepts database connection parameters (database name, hostname, port, username, password), a SQL query input, and configuration options including read-only mode, query timeout, and maximum row limits. When a query execution is requested, the component first validates all connection parameters through the security module—`validate_database_name()` ensures the database name follows identifier rules, `validate_hostname()` checks for valid hostname format and blocks SQL metacharacters, and `validate_port()` confirms the port is within the valid range (1-65535).

Before executing any query, the component performs comprehensive query safety validation using `validate_sql_query_safety()`. In read-only mode (enabled by default for security), only SELECT queries are permitted, preventing accidental data modification. The validation function detects multiple statement attempts (semicolon-separated queries), blocks SQL comments (`--`, `/* */`), and rejects dangerous patterns like EXEC, xp_cmdshell, and chained DROP/DELETE statements. Once validated, the component establishes a connection to DB2 using a properly formatted connection string with SSL/TLS encryption enabled. It sets a configurable query timeout (1-300 seconds) using DB2's `CURRENT_QUERY_TIMEOUT` special register to prevent resource exhaustion from long-running queries. Query results are fetched with a maximum row limit (default 100, configurable up to 10,000) and converted into Langflow `Data` objects for seamless integration with other components. All database errors are caught and sanitized through `create_safe_error_message()`, which maps specific DB2 error codes (SQL30081N, SQL30082N, SQL0204N) to generic user-friendly messages that don't expose sensitive information like table names, credentials, or internal paths. The component ensures proper resource cleanup by closing cursors and connections in finally blocks, even when errors occur.

---

## 3. Secure Connection Technique

**SSL/TLS Encryption:**

Both components enforce encrypted connections to IBM DB2 using SSL/TLS protocols. The connection string includes `PROTOCOL=TCPIP` and automatically negotiates the highest available TLS version supported by both client and server. This ensures all data transmitted between Langflow and DB2—including credentials, query text, and result sets—is encrypted in transit, protecting against man-in-the-middle attacks and network eavesdropping.

**Credential Management:**

The integration implements a strict separation between sensitive and non-sensitive configuration data. Database names, hostnames, and usernames are stored as **Generic-typed** global variables in Langflow, which are treated as configuration data and can be logged for debugging. Passwords, however, must use **Credential-typed** global variables, which are encrypted at rest in Langflow's storage and masked in the UI. The components validate this separation at runtime—attempting to use a Credential-typed variable for a non-password field raises a validation error, preventing accidental credential exposure in logs or error messages. This design follows the principle of least privilege and ensures compliance with security standards for credential management.

**Connection String Security:**

Connection strings are constructed programmatically with validated parameters, never from user-provided strings. The format follows IBM DB2's standard: `DATABASE={db};HOSTNAME={host};PORT={port};PROTOCOL=TCPIP;UID={user};PWD={password}`. Each parameter is validated before inclusion—identifiers are checked against reserved keywords and malicious patterns, hostnames are validated for proper format, and ports are range-checked. The password is the only parameter that bypasses validation (as it can contain any characters) but is never logged or included in error messages. This approach eliminates the risk of connection string injection attacks.

**Defense-in-Depth Security Layers:**

The security architecture implements four independent validation layers that work together to prevent SQL injection and unauthorized access:

1. **Input Validation Layer** - All identifiers (table names, column names, database names) are validated using regex patterns that allow only alphanumeric characters, underscores, and dollar signs, with a maximum length of 128 characters. Reserved SQL keywords (200+ keywords including SELECT, DROP, TABLE) are blocked. Hostnames are validated for proper format and checked for SQL metacharacters.

2. **SQL Injection Prevention Layer** - Query text is analyzed for dangerous patterns before execution. The system detects multiple statement attempts (semicolons followed by SQL keywords), blocks SQL comments (`--`, `/* */`), and rejects dangerous stored procedures (xp_cmdshell, EXEC). In read-only mode, only SELECT operations are permitted through operation whitelisting.

3. **String Sanitization Layer** - All string values inserted into queries are sanitized using SQL standard escaping—single quotes are doubled (`'` becomes `''`). Identifiers are wrapped in double quotes to prevent interpretation as SQL keywords. This layer operates even after validation to provide defense-in-depth.

4. **Error Message Sanitization Layer** - All exceptions are caught and processed through `create_safe_error_message()`, which maps specific DB2 error codes to generic messages. For example, authentication failures (SQL30082N) become "Authentication failed: Invalid username or password" without revealing the attempted username. Table not found errors (SQL0204N) become "Table or view not found" without exposing schema information. This prevents information disclosure through error messages.

**Query Timeout Protection:**

Both components implement configurable query timeouts (default 30 seconds, range 1-300 seconds) to prevent resource exhaustion from runaway queries. The timeout is enforced at the database level using DB2's `SET CURRENT_QUERY_TIMEOUT` command, ensuring that even if the client connection hangs, the database will terminate the query and free resources. This protects against both accidental infinite loops and deliberate denial-of-service attempts through expensive queries.

**Audit Trail:**

All database operations are logged with sanitized information—successful connections, query execution (with query type but not full text), row counts, and error types (but not error details). This provides an audit trail for security monitoring while ensuring sensitive data is never written to logs. The logging follows the principle of "log what happened, not what was attempted" to prevent log injection attacks.

---

## Summary

The IBM DB2 integration provides enterprise-grade security through a carefully designed class hierarchy where high-level Langflow components (`DB2VectorStoreComponent`, `DB2SQLComponent`) handle user interaction and data formatting, core implementation classes (`DB2VS`) manage database operations with proper parameterization, and a shared security module (`db2_security`) enforces validation at every layer. Secure connections are established using SSL/TLS encryption, credentials are properly segregated and encrypted, and multiple independent security layers work together to prevent SQL injection, unauthorized access, and information disclosure. This architecture ensures that the integration is production-ready for enterprise environments with strict security requirements.

---

**Files Reference:**
- Vector Component: `src/lfx/src/lfx/components/ibm/db2_vector.py`
- Vector Core: `src/lfx/src/lfx/components/ibm/db2vs.py`
- SQL Component: `src/lfx/src/lfx/components/ibm/db2_sql.py`
- Security Module: `src/lfx/src/lfx/components/ibm/db2_security.py`
- Tests: `src/backend/tests/unit/components/ibm/`