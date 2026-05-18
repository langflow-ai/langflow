"""IBM Db2 SQL Component for Langflow."""

from lfx.components.ibm.db2_security import (
    create_safe_error_message,
    validate_database_name,
    validate_hostname,
    validate_port,
    validate_sql_query_safety,
)
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, HandleInput, IntInput, SecretStrInput, StrInput
from lfx.io import Output
from lfx.schema.data import Data


class DB2SQLComponent(Component):
    """IBM Db2 SQL Executor Component with security validations."""

    display_name = "IBM Db2 SQL"
    description = (
        "Execute SQL queries on IBM Db2 database with security controls. "
        "Use Generic-typed global variables for connection parameters (database, hostname, username). "
        "Only password should use Credential-typed variables."
    )
    documentation = "https://www.ibm.com/docs/en/db2/11.5"
    icon = "DB2"
    name = "DB2SQL"

    inputs = [
        StrInput(
            name="database",
            display_name="Database Name",
            required=True,
            info="Name of the Db2 database. Use a Generic-typed global variable or direct input. "
            "Credential-typed variables are not allowed for database names.",
        ),
        StrInput(
            name="hostname",
            display_name="Hostname",
            required=True,
            info="Db2 server hostname or IP address. Use a Generic-typed global variable or direct input.",
        ),
        IntInput(
            name="port",
            display_name="Port",
            value=50000,
            required=True,
            info="Db2 server port (default: 50000)",
        ),
        StrInput(
            name="username",
            display_name="Username",
            required=True,
            info="Db2 database username. Use a Generic-typed global variable or direct input.",
        ),
        SecretStrInput(
            name="password",
            display_name="Password",
            required=True,
            info="Db2 database password",
        ),
        HandleInput(
            name="sql_query",
            display_name="SQL Query",
            input_types=["Message", "Text", "Data"],
            required=False,
            info="SQL query to execute (SELECT queries recommended for safety)",
        ),
        IntInput(
            name="max_rows",
            display_name="Max Rows",
            value=100,
            info="Maximum number of rows to return (1-10000)",
            advanced=True,
        ),
        BoolInput(
            name="read_only_mode",
            display_name="Read-Only Mode",
            value=True,
            advanced=True,
            info="If enabled, only SELECT queries are allowed (recommended for security)",
        ),
        IntInput(
            name="query_timeout",
            display_name="Query Timeout (seconds)",
            value=30,
            advanced=True,
            info="Maximum time allowed for query execution (1-300 seconds)",
        ),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="execute_query"),
    ]

    def execute_query(self) -> list[Data]:
        """Execute SQL query on Db2 database with security validations.

        Returns:
            List of Data objects containing query results

        Raises:
            ImportError: If DB2 packages are not installed
            ValueError: If inputs are invalid or query is unsafe
            ConnectionError: If database connection fails
            RuntimeError: If query execution fails
        """
        try:
            import ibm_db_dbi
        except ImportError as e:
            msg = "Could not import required DB2 packages. Please install ibm_db and ibm_db_dbi."
            raise ImportError(msg) from e

        # SECURITY: Validate all inputs
        try:
            validated_database = validate_database_name(self.database)
            validated_hostname = validate_hostname(self.hostname)
            validated_port = validate_port(self.port)
        except ValueError as e:
            msg = f"Invalid connection parameters: {e}"
            raise ValueError(msg) from e

        if not self.username or not self.password:
            msg = "Missing required credentials: username and password are required"
            raise ValueError(msg)

        if not self.sql_query:
            msg = "SQL Query is required. Please provide a SQL query to execute."
            raise ValueError(msg)

        # Extract query text if it's a Data or Message object
        query_text = self.sql_query
        if hasattr(self.sql_query, "text"):
            query_text = self.sql_query.text
        elif hasattr(self.sql_query, "data") and isinstance(self.sql_query.data, dict):
            query_text = self.sql_query.data.get("text", str(self.sql_query.data))
        elif isinstance(self.sql_query, Data):
            query_text = str(self.sql_query.data)

        # SECURITY: Validate query safety
        try:
            if self.read_only_mode:
                # In read-only mode, only allow SELECT queries
                validate_sql_query_safety(query_text, allowed_operations={"SELECT"})
            else:
                # In read-write mode, validate but allow more operations
                validate_sql_query_safety(query_text)
        except ValueError as e:
            msg = f"Query validation failed: {e}"
            self.log(f"Rejected unsafe query: {query_text[:100]}...")
            raise ValueError(msg) from e

        # Validate max_rows
        max_rows_limit = 10000
        if self.max_rows < 1 or self.max_rows > max_rows_limit:
            msg = f"max_rows must be between 1 and {max_rows_limit}"
            raise ValueError(msg)

        # Validate query_timeout
        max_timeout = 300
        if self.query_timeout < 1 or self.query_timeout > max_timeout:
            msg = f"query_timeout must be between 1 and {max_timeout} seconds"
            raise ValueError(msg)

        try:
            # Create connection string with validated parameters
            conn_str = (
                f"DATABASE={validated_database};"
                f"HOSTNAME={validated_hostname};"
                f"PORT={validated_port};"
                f"PROTOCOL=TCPIP;"
                f"UID={self.username};"
                f"PWD={self.password};"
            )

            # Connect to Db2
            conn = ibm_db_dbi.connect(conn_str, "", "")
            self.log(f"Connected to Db2 database: {validated_database}")

            # Execute query with timeout
            cursor = conn.cursor()
            try:
                # Set query timeout using DB2 special register
                cursor.execute(f"SET CURRENT QUERY_TIMEOUT = {self.query_timeout}")
                self.log(f"Set query timeout to {self.query_timeout} seconds")

                cursor.execute(query_text)
                self.log("Executed query successfully")

                # Fetch results
                if cursor.description:
                    # Query returns results (SELECT)
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchmany(self.max_rows)

                    self.log(f"Query returned {len(rows)} rows")

                    # Convert to Data objects
                    results = []
                    for row in rows:
                        row_dict = dict(zip(columns, row, strict=False))
                        data = Data(data=row_dict)
                        results.append(data)

                    self.status = f"Retrieved {len(results)} rows"
                    return results
                # Query doesn't return results (INSERT, UPDATE, DELETE)
                conn.commit()
                affected_rows = cursor.rowcount

                self.log(f"Query affected {affected_rows} rows")
                self.status = f"Query executed successfully. Affected {affected_rows} rows"

                # Return result with status
                return [Data(data={"status": "success", "affected_rows": affected_rows})]
            finally:
                cursor.close()
                conn.close()

        except ibm_db_dbi.DatabaseError as e:
            # Database-specific errors with safe messages
            safe_msg = create_safe_error_message(e, "during query execution")
            self.log(f"Database error: {safe_msg}")
            raise RuntimeError(safe_msg) from e
        except Exception as e:
            # Generic errors with safe messages
            safe_msg = create_safe_error_message(e, "during query execution")
            self.log(f"Error: {safe_msg}")
            raise RuntimeError(safe_msg) from e


# Made with Bob
