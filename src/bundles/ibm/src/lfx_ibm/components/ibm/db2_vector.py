"""IBM Db2 Vector Store Component for Langflow."""

import contextlib
from pathlib import Path
from typing import Any

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.inputs.inputs import BoolInput, DropdownInput, HandleInput, IntInput, SecretStrInput, StrInput
from lfx.io import Output, QueryInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx_ibm.components.ibm.db2_security import (
    create_safe_error_message,
    validate_and_prepare_ssl_certificate,
    validate_database_name,
    validate_hostname,
    validate_identifier,
    validate_port,
)


class DB2VectorStoreComponent(LCVectorStoreComponent):
    """IBM Db2 Vector Store with search capabilities."""

    display_name: str = "IBM Db2 Vector Store"
    description: str = (
        "IBM Db2 Vector Store with search capabilities. "
        "Use Generic-typed global variables for connection parameters (database, hostname, username). "
        "Only password should use Credential-typed variables."
    )
    documentation: str = "https://www.ibm.com/docs/en/db2/11.5"
    name = "DB2VectorStore"
    icon = "DB2"

    inputs = [
        StrInput(
            name="collection_name",
            display_name="Table Name",
            value="LANGFLOW_VECTORS",
            required=True,
            info="Name of the DB2 table to store vectors (will be created if it doesn't exist)",
        ),
        HandleInput(
            name="embedding",
            display_name="Embedding Model",
            input_types=["Embeddings"],
            required=True,
            info="Embedding model to use for vectorization",
        ),
        HandleInput(
            name="ingest_data",
            display_name="Ingest Data",
            input_types=["Data", "DataFrame", "Table"],
            is_list=True,
            info="Data to ingest into the vector store. Accepts Data objects, DataFrame, and Table.",
        ),
        QueryInput(
            name="search_query",
            display_name="Search Query",
            info="Enter a query to run a similarity search.",
            placeholder="Enter a query...",
            tool_mode=True,
        ),
        # DB2 Connection Credentials (Advanced Settings)
        StrInput(
            name="database",
            display_name="Database Name",
            required=True,
            advanced=True,
            info="Name of the Db2 database. Use a Generic-typed global variable or direct input. "
            "Credential-typed variables are not allowed for database names.",
        ),
        StrInput(
            name="hostname",
            display_name="Hostname",
            required=True,
            advanced=True,
            info="Db2 server hostname or IP address. Use a Generic-typed global variable or direct input.",
        ),
        IntInput(
            name="port",
            display_name="Port",
            value=50000,
            required=True,
            advanced=True,
            info="Db2 server port (default: 50000)",
        ),
        StrInput(
            name="username",
            display_name="Username",
            required=True,
            advanced=True,
            info="Db2 database username. Use a Generic-typed global variable or direct input.",
        ),
        SecretStrInput(
            name="password",
            display_name="Password",
            required=True,
            advanced=True,
            info="Db2 database password",
        ),
        # SSL/TLS Configuration
        BoolInput(
            name="use_ssl",
            display_name="Use SSL/TLS",
            value=False,
            advanced=True,
            real_time_refresh=True,
            info="Enable SSL/TLS encryption for database connection. Recommended for production environments.",
        ),
        StrInput(
            name="ssl_certificate_path",
            display_name="SSL Certificate Path",
            required=False,
            advanced=True,
            info=(
                "Path to SSL certificate file (.crt, .pem, .cer) or URL to download certificate. "
                "Supports local paths (relative/absolute) and URLs (https://...). "
                "Required when SSL/TLS is enabled."
            ),
        ),
        SecretStrInput(
            name="ssl_certificate_password",
            display_name="SSL Certificate Password",
            required=False,
            advanced=True,
            info=(
                "Optional: Password for password-protected SSL certificate/keystore. "
                "Only required if your certificate file is encrypted with a password."
            ),
        ),
        # Advanced Settings
        BoolInput(
            name="should_cache_vector_store",
            display_name="Cache Vector Store",
            value=True,
            advanced=True,
            info="If True, the vector store will be cached for the current build of the component.",
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["Similarity", "MMR"],
            value="Similarity",
            advanced=True,
            info="Type of search to perform",
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            value=4,
            advanced=True,
            info="Number of results to return from search",
        ),
        DropdownInput(
            name="distance_strategy",
            display_name="Distance Strategy",
            options=["COSINE", "EUCLIDEAN_DISTANCE", "DOT_PRODUCT"],
            value="COSINE",
            advanced=True,
            info="Distance calculation strategy",
        ),
        BoolInput(
            name="use_bulk_insert",
            display_name="Use Bulk Insert",
            value=True,
            advanced=True,
            info=(
                "Enable bulk insert using executemany() for better performance. "
                "When enabled, all documents are inserted in a single batch (unlimited chunk size). "
                "When disabled, uses row-by-row insert with execute() (chunk size: 1 document per call)."
            ),
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
            method="perform_search",
        ),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
        """Update build configuration to show/hide SSL fields based on use_ssl toggle."""
        if field_name == "use_ssl":
            # Show/hide SSL certificate fields based on use_ssl value
            build_config["ssl_certificate_path"]["show"] = field_value
            build_config["ssl_certificate_password"]["show"] = field_value
        return build_config

    def perform_search(self) -> DataFrame:
        """Return search results as a DataFrame."""
        from lfx.schema.dataframe import DataFrame

        # Get search results
        results = self.search_documents()

        # Return DataFrame wrapping the Data objects
        # DataFrame constructor will handle Data objects properly
        return DataFrame(results)

    def _add_documents_to_vector_store(self, vector_store) -> None:
        """Adds documents to the Vector Store."""
        if not self.ingest_data:
            self.status = ""
            return

        # Convert DataFrame to Data if needed using parent's method
        ingest_data = self._prepare_ingest_data()

        # Duplicate checking is performed at ingestion time by comparing
        # document content in the current batch. Database-level duplicate detection
        # would require querying existing documents, which is not currently implemented.
        documents_to_add = []
        seen_documents = set()

        for _input in ingest_data or []:
            if isinstance(_input, Data):
                # Create a hashable representation for duplicate detection
                doc_content = _input.text if hasattr(_input, "text") else str(_input.data)

                # Always prevent duplicates
                if doc_content not in seen_documents:
                    documents_to_add.append(_input.to_lc_document())
                    seen_documents.add(doc_content)
            else:
                msg = "Vector Store Inputs must be Data objects."
                raise TypeError(msg)

        # Add documents with minimal metadata only to avoid storing file/session-related fields.
        if documents_to_add and self.embedding is not None:
            self.log(f"Adding {len(documents_to_add)} documents to the Vector Store.")
            try:
                from langchain_community.vectorstores.utils import filter_complex_metadata

                filtered_documents = filter_complex_metadata(documents_to_add)
                minimal_documents = []
                for doc in filtered_documents:
                    doc.metadata = {}
                    minimal_documents.append(doc)
                vector_store.add_documents(minimal_documents)
            except ImportError:
                self.log("Warning: Could not import filter_complex_metadata. Adding documents with stripped metadata.")
                minimal_documents = []
                for doc in documents_to_add:
                    doc.metadata = {}
                    minimal_documents.append(doc)
                vector_store.add_documents(minimal_documents)
        else:
            self.log("No documents to add to the Vector Store.")

    @check_cached_vector_store
    def build_vector_store(self):  # type: ignore[override]
        """Build and return the DB2 vector store instance."""
        try:
            import ibm_db_dbi
            from langchain_community.vectorstores.utils import DistanceStrategy
            from lfx_ibm.components.ibm.db2vs import DB2VS
        except ImportError as e:
            msg = "Could not import required DB2 packages. Please install ibm_db and ibm_db_dbi."
            raise ImportError(msg) from e

        # SECURITY: Validate all connection parameters
        try:
            validated_database = validate_database_name(self.database)
            validated_hostname = validate_hostname(self.hostname)
            validated_port = validate_port(self.port)
            validated_table_name = validate_identifier(self.collection_name, "table name")
        except ValueError as e:
            msg = f"Invalid connection parameters: {e}"
            raise ValueError(msg) from e

        if not self.username or not self.password:
            msg = "Missing required credentials: username and password are required"
            raise ValueError(msg)

        # Handle SSL certificate if provided
        ssl_cert_path = None
        is_temp_cert = False
        temp_cert_cleanup = None

        if self.use_ssl:
            self.log("SSL/TLS enabled for database connection")

            # Validate that certificate path is provided when SSL is enabled
            cert_path_input = getattr(self, "ssl_certificate_path", None)
            if not cert_path_input or not cert_path_input.strip():
                msg = (
                    "SSL/TLS is enabled but no certificate path provided. "
                    "Please provide the SSL certificate path or disable SSL/TLS."
                )
                self.log(f"❌ {msg}")
                raise ValueError(msg)

            # Validate and prepare SSL certificate
            self.log(f"Validating SSL certificate: {cert_path_input}")
            ssl_cert_path, is_temp_cert, cert_error = validate_and_prepare_ssl_certificate(cert_path_input)

            if cert_error:
                msg = f"SSL certificate validation failed: {cert_error}"
                self.log(f"❌ {msg}")
                raise ValueError(msg)

            if is_temp_cert:
                self.log(f"Downloaded SSL certificate to temporary file: {ssl_cert_path}")
                temp_cert_cleanup = ssl_cert_path
            else:
                self.log(f"Using SSL certificate: {ssl_cert_path}")
        else:
            self.log("SSL/TLS disabled - connecting without encryption")

        # Create connection string with validated parameters
        conn_str = (
            f"DATABASE={validated_database};"
            f"HOSTNAME={validated_hostname};"
            f"PORT={validated_port};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.username};"
            f"PWD={self.password};"
        )

        # Add SSL parameters if enabled
        if self.use_ssl:
            conn_str += "SECURITY=SSL;"
            if ssl_cert_path:
                # Use SSLServerCertificate parameter for DB2
                conn_str += f"SSLServerCertificate={ssl_cert_path};"

                # Add certificate password if provided
                ssl_cert_password = getattr(self, "ssl_certificate_password", None)
                if ssl_cert_password and ssl_cert_password.strip():
                    conn_str += f"SSLClientKeystorePassword={ssl_cert_password};"
                    self.log("SSL connection configured with custom certificate and password")
                else:
                    self.log("SSL connection configured with custom certificate (no password)")
            else:
                self.log("SSL connection configured with system certificates")

        # Create connection with safe error handling
        try:
            connection = ibm_db_dbi.connect(conn_str, "", "")
            self.log(f"✓ Connected to DB2 database: {validated_database}")

            # Clean up temporary certificate file if it was downloaded
            if temp_cert_cleanup:
                try:
                    Path(temp_cert_cleanup).unlink(missing_ok=True)
                    self.log("Cleaned up temporary certificate file")
                except OSError as cleanup_error:
                    self.log(f"Warning: Could not clean up temporary certificate: {cleanup_error}")

        except Exception as e:
            # Clean up temporary certificate on connection failure
            if temp_cert_cleanup:
                with contextlib.suppress(OSError):
                    Path(temp_cert_cleanup).unlink(missing_ok=True)

            # SECURITY: Use safe error messages that don't expose sensitive info
            safe_msg = create_safe_error_message(e, "while connecting to database")
            self.log(f"❌ Connection failed: {safe_msg}")
            raise ConnectionError(safe_msg) from e

        # Map distance strategy
        distance_strategy_map = {
            "COSINE": DistanceStrategy.COSINE,
            "EUCLIDEAN_DISTANCE": DistanceStrategy.EUCLIDEAN_DISTANCE,
            "DOT_PRODUCT": DistanceStrategy.DOT_PRODUCT,
        }

        try:
            # Validate embedding model is provided
            if not self.embedding:
                msg = (
                    "❌ Embedding Model Required\n\n"
                    "Please connect an embedding model to the 'Embedding Model' input.\n"
                    "This is required to generate embeddings for your data."
                )
                raise ValueError(msg)

            # Log bulk insert mode
            bulk_insert_enabled = getattr(self, "use_bulk_insert", True)
            insert_mode = "bulk insert (executemany)" if bulk_insert_enabled else "row-by-row insert (execute)"
            self.log(f"Insert mode: {insert_mode}")

            # Build vector store (will automatically generate embeddings for existing empty rows)
            self.log(f"Connecting to DB2 table: {validated_table_name}")
            vector_store = DB2VS(
                client=connection,
                embedding_function=self.embedding,
                table_name=validated_table_name,
                distance_strategy=distance_strategy_map.get(self.distance_strategy, DistanceStrategy.COSINE),
                use_bulk_insert=bulk_insert_enabled,
            )

            self.log(f"Connected to DB2 table: {validated_table_name}")

            # Add documents if provided - SIMPLIFIED like Chroma
            self._add_documents_to_vector_store(vector_store)
        except Exception:
            # Ensure connection is closed on error
            connection.close()
            raise

        return vector_store

    def search_documents(self) -> list[Data]:
        """Perform similarity search and return results.

        The vector store is built first so that any connected ingest data is
        written to DB2 regardless of whether a search query is provided.
        Ingestion and search are independent: an empty query simply skips the
        search and returns no results -- it must not skip ingestion.
        """
        # Build (and ingest into) the vector store first. ``build_vector_store``
        # is what writes ``self.ingest_data`` to DB2, so it has to run even when
        # no search query is supplied -- otherwise ingestion would silently
        # depend on a query being present. Mirrors LCVectorStoreComponent.
        vector_store = self.build_vector_store()

        if not self.search_query:
            self.status = ""
            return []

        # Extract text from search_query (handle Message, Data, or string)
        query_text = self.search_query
        if hasattr(self.search_query, "text"):
            # Handle Message objects
            query_text = self.search_query.text
        elif isinstance(self.search_query, Data):
            # Handle Data objects - try different attributes
            if hasattr(self.search_query, "text_data") and self.search_query.text_data:
                query_text = self.search_query.text_data
            elif hasattr(self.search_query, "data") and self.search_query.data:
                # If data is a dict or JSON, convert to string
                if isinstance(self.search_query.data, dict):
                    # Extract text from common fields
                    query_text = (
                        self.search_query.data.get("text")
                        or self.search_query.data.get("content")
                        or self.search_query.data.get("query")
                        or str(self.search_query.data)
                    )
                else:
                    query_text = str(self.search_query.data)
            else:
                query_text = str(self.search_query)
        elif not isinstance(self.search_query, str):
            # Convert any other type to string
            query_text = str(self.search_query)

        # Perform search based on search type
        if self.search_type == "Similarity":
            docs = vector_store.similarity_search(
                query=query_text,
                k=self.number_of_results,
            )
        else:  # MMR
            docs = vector_store.max_marginal_relevance_search(
                query=query_text,
                k=self.number_of_results,
            )

        results = [Data(text=doc.page_content, data={"text": doc.page_content}) for doc in docs]
        self.status = results
        return results

    def build(self):  # type: ignore[override]
        """Build the component based on the selected mode."""
        mode = getattr(self, "mode", "Ingest")

        if mode == "Search":
            # Search mode: return search results
            return self.search_documents()
        if mode == "Vector Store":
            # Vector Store mode: return the vector store instance
            return self.build_vector_store()
        # Ingest mode (default): build vector store with data ingestion
        return self.build_vector_store()


# Made with Bob
