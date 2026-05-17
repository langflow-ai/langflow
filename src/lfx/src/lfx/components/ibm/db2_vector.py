import contextlib
from typing import Any

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, SecretStrInput, StrInput
from lfx.io import HandleInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

AnyStrInput: Any = StrInput
AnyHandleInput: Any = HandleInput
AnyIntInput: Any = IntInput
AnySecretStrInput: Any = SecretStrInput
AnyBoolInput: Any = BoolInput
AnyDropdownInput: Any = DropdownInput

# Constants for validation
MAX_TABLE_NAME_LENGTH = 64
MIN_PORT = 1
MAX_PORT = 65535
DEFAULT_DB2_PORT = 50000


class DB2VectorStoreComponent(LCVectorStoreComponent):
    """IBM Db2 Vector Store with vector similarity search."""

    display_name: str | None = "IBM Db2 Vector Store"
    description: str | None = "IBM Db2 Vector Store for vector similarity search"
    documentation: str | None = "https://www.ibm.com/docs/en/db2/11.5"
    name = "DB2VectorStore"
    icon = "DB2"

    inputs = [  # type: ignore[call-arg]  # Framework input classes accept dynamic kwargs at runtime, but stubs/signatures are incomplete
        # Core inputs (2)
        AnyStrInput(
            name="collection_name",
            display_name="Table Name",
            value="LANGFLOW_VECTORS",
            required=True,
            info="Name of the DB2 table to store vectors (will be created if it doesn't exist)",
        ),
        *LCVectorStoreComponent.inputs,
        AnyHandleInput(
            name="embedding",
            display_name="Embedding Model",
            input_types=["Embeddings"],
            required=True,
            info="Embedding model to use for vectorization",
        ),
        # Core connection inputs (5)
        AnyStrInput(
            name="database",
            display_name="Database Name",
            required=True,
            info="Name of the DB2 database",
            advanced=True,
        ),
        AnyStrInput(
            name="hostname",
            display_name="Hostname",
            value="localhost",
            required=True,
            info="DB2 server hostname or IP address",
            advanced=True,
        ),
        AnyIntInput(
            name="port",
            display_name="Port",
            value=50000,
            required=True,
            info="DB2 server port (valid range: 1-65535)",
            advanced=True,
        ),
        AnyStrInput(
            name="username",
            display_name="Username",
            required=True,
            info="DB2 username",
            advanced=True,
        ),
        AnySecretStrInput(
            name="password",
            display_name="Password",
            required=True,
            info="DB2 password",
            advanced=True,
        ),
        # Security inputs (2)
        AnyBoolInput(
            name="use_ssl",
            display_name="Use SSL/TLS",
            value=False,
            advanced=True,
            info=(
                "Enable SSL/TLS encryption for secure connections to DB2. "
                "Requires SSL to be configured on the DB2 server. "
                "Note: SSL typically uses port 50001 instead of 50000."
            ),
        ),
        AnyIntInput(
            name="connection_timeout",
            display_name="Connection Timeout (seconds)",
            value=10,
            advanced=True,
            info="Time in seconds to wait for a connection to DB2. Reduced to 10s for faster error feedback.",
        ),
        # Search options (3)
        AnyIntInput(
            name="number_of_results",
            display_name="Number of Results",
            value=4,
            info="Number of results to return from search",
            advanced=True,
        ),
        AnyDropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["Similarity", "MMR"],
            value="Similarity",
            info="Type of search to perform",
            advanced=True,
        ),
        AnyDropdownInput(
            name="distance_strategy",
            display_name="Distance Strategy",
            options=["COSINE", "EUCLIDEAN_DISTANCE", "DOT_PRODUCT"],
            value="COSINE",
            info="Distance calculation strategy",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Search Results",
            name="search_results",
            method="search_documents",
        ),
        Output(
            display_name="Table",
            name="dataframe",
            method="as_dataframe",
        ),
    ]

    def _validate_table_name(self, table_name: str) -> str:
        """Validate table name to prevent SQL injection and ensure DB2 compatibility.

        Security measures:
        - Length limit to prevent ReDoS attacks
        - Character whitelist (alphanumeric + underscore only)
        - No SQL keywords or special characters
        - Prevents command injection through table names

        Args:
            table_name: The table name to validate

        Returns:
            Normalized (stripped) table name

        Raises:
            ValueError: If table name is invalid or potentially dangerous
        """
        if not table_name or not isinstance(table_name, str):
            msg = "Table name cannot be empty"
            raise ValueError(msg)

        # Strip whitespace and return normalized value
        table_name = table_name.strip()

        # Length validation (prevent ReDoS and excessive resource usage)
        # DB2 table name max length is 128, but we use 64 as a safe limit
        if len(table_name) > MAX_TABLE_NAME_LENGTH:
            msg = f"Table name too long (maximum {MAX_TABLE_NAME_LENGTH} characters)"
            raise ValueError(msg)

        if len(table_name) == 0:
            msg = "Table name cannot be empty or whitespace"
            raise ValueError(msg)

        # Character validation - only allow alphanumeric and underscore
        # This prevents SQL injection and special character exploits
        # Using a simple character check instead of regex to avoid ReDoS
        for char in table_name:
            if not (char.isalnum() or char == "_"):
                msg = (
                    f"Table name contains invalid character: '{char}'. "
                    "Only alphanumeric characters and underscores are allowed."
                )
                raise ValueError(msg)

        # Must start with letter or underscore (DB2 requirement)
        if not (table_name[0].isalpha() or table_name[0] == "_"):
            msg = "Table name must start with a letter or underscore"
            raise ValueError(msg)

        # Check for SQL keywords (case-insensitive)
        # This prevents using reserved words that could cause SQL injection
        sql_keywords = {
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "CREATE",
            "ALTER",
            "TABLE",
            "DATABASE",
            "INDEX",
            "VIEW",
            "PROCEDURE",
            "FUNCTION",
            "TRIGGER",
            "GRANT",
            "REVOKE",
            "UNION",
            "JOIN",
            "WHERE",
            "FROM",
            "EXEC",
            "EXECUTE",
            "DECLARE",
            "CURSOR",
            "FETCH",
            "OPEN",
            "CLOSE",
        }

        if table_name.upper() in sql_keywords:
            msg = f"Table name '{table_name}' is a reserved SQL keyword and cannot be used"
            raise ValueError(msg)

        return table_name

    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize a single value for safe storage."""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, (list, tuple)):
            return [self._sanitize_value(v) for v in value]
        if isinstance(value, dict):
            return self._clean_metadata(value)
        # Convert any other type to string representation
        return str(value)

    def _clean_metadata(self, metadata: dict) -> dict:
        """Recursively clean metadata to ensure JSON serializability and security.

        Security measures:
        - Removes null bytes and control characters (XSS prevention)
        - Ensures all values are safe, serializable types
        - Recursively sanitizes nested structures
        - Prevents code injection through metadata

        Args:
            metadata: Dictionary of metadata to clean

        Returns:
            Cleaned metadata dictionary with safe values
        """
        if not isinstance(metadata, dict):
            return {}

        cleaned = {}
        for key, value in metadata.items():
            # Sanitize key (remove special characters that could cause issues)
            safe_key = str(key).replace("\x00", "").replace("\n", "").replace("\r", "")
            if not safe_key:
                continue

            # Sanitize value recursively
            cleaned[safe_key] = self._sanitize_value(value)

        return cleaned

    def _validate_port(self, port: int) -> None:
        """Validate port number is in valid range.

        Security: Prevents invalid port numbers that could cause connection issues
        or be used in port scanning attacks.

        Args:
            port: Port number to validate

        Raises:
            ValueError: If port is not in valid range (1-65535)
        """
        if not isinstance(port, int) or port < MIN_PORT or port > MAX_PORT:
            msg = f"Invalid port number: {port}. Port must be between {MIN_PORT} and {MAX_PORT}."
            raise ValueError(msg)

    def _validate_hostname(self, hostname: str) -> str:
        """Validate hostname format to prevent injection attacks.

        Security measures:
        - Rejects null bytes and control characters
        - Prevents command injection through hostname
        - Ensures hostname is not empty
        - Basic format validation

        Args:
            hostname: Hostname or IP address to validate

        Returns:
            Normalized (stripped) hostname

        Raises:
            ValueError: If hostname is invalid or contains dangerous characters
        """
        if not hostname or not isinstance(hostname, str):
            msg = "Hostname cannot be empty"
            raise ValueError(msg)

        # Basic validation - allow hostnames, IPs, and localhost
        hostname = hostname.strip()
        if not hostname:
            msg = "Hostname cannot be empty or whitespace"
            raise ValueError(msg)

        # Check for null bytes or other dangerous characters
        if "\x00" in hostname or "\n" in hostname or "\r" in hostname:
            msg = "Hostname contains invalid characters"
            raise ValueError(msg)

        return hostname

    def _escape_connection_string_value(self, value: str) -> str:
        """Escape special characters in connection string values to prevent injection.

        Security measures:
        - Removes null bytes and control characters
        - Prevents SQL injection through connection string
        - Rejects semicolons (DB2 connection string delimiter)
        - Ensures safe value formatting

        DB2 connection strings use semicolons as delimiters, so we need to handle
        values that might contain semicolons or other special characters.

        Args:
            value: Connection string value to escape

        Returns:
            Escaped and validated value

        Raises:
            ValueError: If value contains semicolons or other dangerous characters
        """
        if not isinstance(value, str):
            value = str(value)

        # Remove null bytes and control characters
        value = value.replace("\x00", "").replace("\n", "").replace("\r", "")

        # If value contains semicolon, it needs special handling
        # DB2 doesn't support quoting in connection strings, so we reject values with semicolons
        if ";" in value:
            msg = "Connection string values cannot contain semicolons"
            raise ValueError(msg)

        return value

    def _validate_ssl_config(self) -> None:
        """Validate SSL configuration and warn about common issues.

        This helps users identify SSL configuration problems before attempting
        connection, providing faster feedback than waiting for timeout.
        """
        if not self.use_ssl:
            return

        # Warn about port mismatch - SSL typically uses 50001
        if self.port == DEFAULT_DB2_PORT:
            self.log(
                f"Warning: SSL/TLS is enabled but using port {DEFAULT_DB2_PORT}. "
                "DB2 SSL connections typically use port 50001. "
                "If connection fails, try changing the port to 50001."
            )

        # Info about SSL connection
        self.log(
            "Info: Connecting with SSL/TLS enabled (SECURITY=SSL). "
            "For IBM Cloud DB2 or properly configured SSL servers, "
            "no additional certificate parameters are needed."
        )

    @check_cached_vector_store
    def build_vector_store(self):  # type: ignore[no-untyped-def]
        """Build and return the DB2 vector store instance.

        Security: All inputs are validated and sanitized before use.
        Credentials are never logged or exposed in error messages.

        Returns:
            DB2VS: The DB2 vector store instance

        Raises:
            ImportError: If IBM DB2 dependencies are not installed
        """
        # Lazy import of IBM-specific dependencies
        try:
            import ibm_db_dbi  # type: ignore[import-untyped]
            from langchain_community.vectorstores.utils import DistanceStrategy
            from langchain_db2.db2vs import DB2VS
        except ImportError as e:
            msg = (
                "IBM DB2 dependencies are not installed. "
                "Install them with: pip install 'lfx[ibm]' or uv sync --extra ibm --package lfx"
            )
            raise ImportError(msg) from e

        # Note: Debug logging removed to prevent any potential credential exposure

        # Validate required connection parameters
        if not self.database:
            msg = "Database name is required"
            raise ValueError(msg)
        if not self.hostname:
            msg = "Hostname is required"
            raise ValueError(msg)

        # Validate and normalize table name (SQL injection prevention + ReDoS protection)
        normalized_table_name = self._validate_table_name(self.collection_name)

        # Validate port number
        self._validate_port(self.port)

        # Validate and normalize hostname format
        normalized_hostname = self._validate_hostname(self.hostname)

        # Validate credentials
        if not self.username:
            msg = "Username is required"
            raise ValueError(msg)
        if not self.password:
            msg = "Password is required"
            raise ValueError(msg)

        # Validate SSL configuration and provide warnings
        self._validate_ssl_config()

        # Escape and validate connection string values to prevent injection
        try:
            safe_database = self._escape_connection_string_value(self.database)
            safe_hostname = self._escape_connection_string_value(normalized_hostname)
        except ValueError as e:
            msg = f"Invalid connection parameter: {e}"
            raise ValueError(msg) from e

        # Build connection string with username/password authentication
        try:
            safe_username = self._escape_connection_string_value(self.username)
            safe_password = self._escape_connection_string_value(self.password)
        except ValueError as e:
            msg = f"Invalid credential parameter: {e}"
            raise ValueError(msg) from e

        conn_str_parts = [
            f"DATABASE={safe_database}",
            f"HOSTNAME={safe_hostname}",
            f"PORT={self.port}",
            "PROTOCOL=TCPIP",
            f"UID={safe_username}",
            f"PWD={safe_password}",
        ]

        # Add SSL/TLS configuration if enabled
        if self.use_ssl:
            conn_str_parts.append("SECURITY=SSL")

        # Add connection timeout
        if self.connection_timeout and self.connection_timeout > 0:
            conn_str_parts.append(f"ConnectTimeout={self.connection_timeout}")

        conn_str = ";".join(conn_str_parts)

        # Create connection with proper error handling and cleanup
        connection = None
        try:
            connection = ibm_db_dbi.connect(conn_str, "", "")
        except Exception as e:
            error_msg = str(e)
            error_msg_lower = error_msg.lower()

            # Log the detailed error internally for debugging
            self.log(f"DB2 connection error: {error_msg}")

            # Check for SSL/TLS specific errors FIRST (most specific)
            if "ssl" in error_msg_lower or "tls" in error_msg_lower or "security" in error_msg_lower:
                # Build detailed SSL error message without exposing raw error
                ssl_hints = [
                    "SSL/TLS connection failed. Common causes:",
                    "1. DB2 server not configured for SSL (check server settings)",
                ]

                # Add port-specific hint
                if self.port == DEFAULT_DB2_PORT:
                    ssl_hints.append(f"2. Wrong port - SSL typically uses port 50001, not {DEFAULT_DB2_PORT}")
                else:
                    ssl_hints.append("2. Incorrect port - verify SSL port with your DB2 administrator")

                ssl_hints.append("3. SSL handshake failed - verify server SSL configuration")

                ssl_hints.append("4. Firewall blocking SSL port")

                msg = "\n".join(ssl_hints)
                raise ConnectionError(msg) from e

            # Translate other DB2-specific error codes to user-friendly messages
            # without exposing sensitive information
            if "SQL30081N" in error_msg or "communication error" in error_msg_lower:
                msg = (
                    "Cannot connect to DB2 server. Please verify:\n"
                    "1. Hostname and port are correct\n"
                    "2. Network connectivity to the server\n"
                    "3. DB2 server is running and accepting connections\n"
                    "4. Firewall allows connections to the port"
                )
                raise ConnectionError(msg) from e
            if "SQL1336N" in error_msg or "not found" in error_msg_lower:
                msg = "Cannot resolve hostname. Please check the hostname or use an IP address."
                raise ConnectionError(msg) from e
            if "SQL30082N" in error_msg or "authentication" in error_msg_lower:
                msg = "Authentication failed. Please verify your username and password."
                raise ConnectionError(msg) from e
            if "SQL0752N" in error_msg or "database not found" in error_msg_lower:
                msg = "Database not found. Please verify the database name."
                raise ConnectionError(msg) from e
            if "timeout" in error_msg_lower or "timed out" in error_msg_lower:
                msg = (
                    f"Connection timeout after {self.connection_timeout} seconds. Please verify:\n"
                    "1. DB2 server is reachable\n"
                    "2. Port is correct and not blocked by firewall\n"
                    "3. Server is not overloaded"
                )
                raise ConnectionError(msg) from e

            # Generic error without exposing details
            msg = "Failed to connect to DB2. Please check your connection parameters."
            raise ConnectionError(msg) from e

        # Map distance strategy
        distance_strategy_map = {
            "COSINE": DistanceStrategy.COSINE,
            "EUCLIDEAN_DISTANCE": DistanceStrategy.EUCLIDEAN_DISTANCE,
            "DOT_PRODUCT": DistanceStrategy.DOT_PRODUCT,
        }

        if not self.embedding:
            # Close connection before raising error
            if connection:
                with contextlib.suppress(Exception):
                    connection.close()
            msg = "Embedding model is required"
            raise ValueError(msg)

        # Build vector store with error handling
        try:
            vector_store = DB2VS(
                client=connection,
                embedding_function=self.embedding,
                table_name=normalized_table_name,
                distance_strategy=distance_strategy_map.get(self.distance_strategy, DistanceStrategy.COSINE),
            )

            # Add documents if provided
            # Use base class method to prepare data - this handles DataFrame conversion
            ingest_data = self._prepare_ingest_data()

            if ingest_data:
                from langchain_core.documents import Document

                documents = []
                for data in ingest_data:
                    if isinstance(data, Data):
                        documents.append(data.to_lc_document())
                    elif isinstance(data, Document):
                        documents.append(data)
                    else:
                        # Convert other types to Document
                        text = str(data) if not hasattr(data, "text") else data.text
                        metadata = {}
                        if hasattr(data, "metadata") and isinstance(data.metadata, dict):
                            metadata = data.metadata
                        documents.append(Document(page_content=text, metadata=metadata))

                if documents:
                    # Clean and sanitize metadata before adding documents
                    # Security: Remove potentially dangerous content from metadata
                    for doc in documents:
                        if hasattr(doc, "metadata") and isinstance(doc.metadata, dict):
                            doc.metadata = self._clean_metadata(doc.metadata)
                        else:
                            doc.metadata = {}

                    try:
                        vector_store.add_documents(documents)
                    except ValueError as e:
                        error_msg = str(e).lower()
                        # Log detailed error internally
                        self.log(f"Document addition error: {e}")
                        if "dimension mismatch" in error_msg or "dimension" in error_msg:
                            msg = (
                                "Embedding dimension mismatch. The table was created with a different "
                                "embedding dimension. Please drop the table or use a different table name."
                            )
                            raise ValueError(msg) from e
                        # Don't expose internal error details
                        msg = "Failed to add documents to vector store. Please check your data format."
                        raise ValueError(msg) from e
                    except Exception as e:
                        # Log detailed error internally
                        self.log(f"Unexpected error adding documents: {e}")
                        # Catch any other exceptions and provide generic error
                        # Security: Don't expose internal error details that could aid attackers
                        msg = "An error occurred while adding documents to the vector store."
                        raise RuntimeError(msg) from e
        except Exception:
            # Close connection on any error during vector store creation
            if connection:
                with contextlib.suppress(Exception):
                    connection.close()
            raise
        else:
            return vector_store

    def search_documents(self) -> list[Data]:
        """Perform vector similarity search and return results.

        Security: Query text is safely extracted and validated before search.
        No user input is directly executed as code.

        Returns:
            List of Data objects containing search results

        Raises:
            ImportError: If IBM DB2 dependencies are not installed
        """
        # Lazy import - needed for type checking in this method
        try:
            import ibm_db_dbi  # type: ignore[import-untyped]  # noqa: F401
            from langchain_db2.db2vs import DB2VS  # noqa: F401
        except ImportError as e:
            msg = (
                "IBM DB2 dependencies are not installed. "
                "Install them with: pip install 'lfx[ibm]' or uv sync --extra ibm --package lfx"
            )
            raise ImportError(msg) from e

        if not self.search_query:
            return []

        # Extract text from search_query (safe type conversion)
        query_text = self.search_query
        if hasattr(self.search_query, "text"):
            query_text = self.search_query.text
        elif isinstance(self.search_query, Data):
            query_text = self.search_query.text_data
        elif not isinstance(self.search_query, str):
            query_text = str(self.search_query)

        # Get vector store (all security validations happen here)
        vector_store = self.build_vector_store()

        # Perform search based on search type
        if self.search_type == "Similarity":
            docs = vector_store.similarity_search(query=query_text, k=self.number_of_results)
        else:  # MMR
            docs = vector_store.max_marginal_relevance_search(query=query_text, k=self.number_of_results)

        return docs_to_data(docs)

    def as_dataframe(self) -> DataFrame:
        """Return search results as DataFrame.

        Returns:
            DataFrame containing search results
        """
        return DataFrame(self.search_documents())


# Made with Bob
