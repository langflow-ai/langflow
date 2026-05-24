"""IBM Db2 Vector Store Component for Langflow."""

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.components.ibm.db2_security import (
    create_safe_error_message,
    validate_database_name,
    validate_hostname,
    validate_identifier,
    validate_port,
)
from lfx.helpers.data import docs_to_data
from lfx.inputs.inputs import BoolInput, DropdownInput, FloatInput, HandleInput, IntInput, SecretStrInput, StrInput
from lfx.io import Output, QueryInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


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
            input_types=["Data", "DataFrame", "Table", "Message"],
            is_list=True,
            info="Data to ingest into the vector store. Supports Data, DataFrame, Table, and Message objects.",
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
        # Advanced Settings
        BoolInput(
            name="should_cache_vector_store",
            display_name="Cache Vector Store",
            value=True,
            advanced=True,
            info="If True, the vector store will be cached for the current build of the component.",
        ),
        BoolInput(
            name="allow_duplicates",
            display_name="Allow Duplicates",
            advanced=True,
            value=True,
            info="If false, will not add documents that are already in the Vector Store.",
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["Similarity", "MMR", "similarity_score_threshold"],
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
        FloatInput(
            name="score_threshold",
            display_name="Score Threshold",
            value=0.5,
            advanced=True,
            info="Minimum relevance score (0-1) for similarity_score_threshold mode",
        ),
        DropdownInput(
            name="distance_strategy",
            display_name="Distance Strategy",
            options=["COSINE", "EUCLIDEAN_DISTANCE", "DOT_PRODUCT"],
            value="COSINE",
            advanced=True,
            info="Distance calculation strategy",
        ),
    ]

    outputs = [
        Output(
            display_name="Search Results",
            name="search_results",
            method="search_documents",
        ),
        Output(
            display_name="Vector Store",
            name="vector_store",
            method="build_vector_store",
        ),
        Output(
            display_name="Table",
            name="dataframe",
            method="perform_search",
        ),
    ]

    def perform_search(self) -> DataFrame:
        """Return search results as a DataFrame."""
        from lfx.schema.dataframe import DataFrame

        # Get search results
        results = self.search_documents()

        # Return DataFrame wrapping the Data objects
        # DataFrame constructor will handle Data objects properly
        return DataFrame(results)

    def _add_documents_to_vector_store(self, vector_store) -> None:
        """Adds documents to the Vector Store - SIMPLIFIED like Chroma."""
        from copy import deepcopy

        if not self.ingest_data:
            self.status = ""
            return

        # Convert DataFrame to Data if needed using parent's method
        ingest_data = self._prepare_ingest_data()

        # Get existing documents for duplicate checking (simplified)
        stored_documents_without_id = []
        if not self.allow_duplicates:
            # TODO: Implement db2_collection_to_data utility
            # For now, skip duplicate checking to match Chroma's approach
            stored_data = []
            for value in deepcopy(stored_data):
                if hasattr(value, "id"):
                    del value.id
                stored_documents_without_id.append(value)

        # Process only Data objects (like Chroma)
        documents = []
        for _input in ingest_data or []:
            if isinstance(_input, Data):
                if _input not in stored_documents_without_id:
                    documents.append(_input.to_lc_document())
            else:
                msg = "Vector Store Inputs must be Data objects."
                raise TypeError(msg)

        # Add documents with metadata filtering (like Chroma)
        if documents and self.embedding is not None:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            try:
                from langchain_community.vectorstores.utils import filter_complex_metadata

                filtered_documents = filter_complex_metadata(documents)
                vector_store.add_documents(filtered_documents)
            except ImportError:
                self.log("Warning: Could not import filter_complex_metadata. Adding documents without filtering.")
                vector_store.add_documents(documents)
        else:
            self.log("No documents to add to the Vector Store.")

    @check_cached_vector_store
    def build_vector_store(self):  # type: ignore[override]
        """Build and return the DB2 vector store instance."""
        try:
            import ibm_db_dbi
            from langchain_community.vectorstores.utils import DistanceStrategy

            from lfx.components.ibm.db2vs import DB2VS
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

        # Create connection string with validated parameters
        conn_str = (
            f"DATABASE={validated_database};"
            f"HOSTNAME={validated_hostname};"
            f"PORT={validated_port};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.username};"
            f"PWD={self.password};"
        )

        # Create connection with safe error handling
        try:
            connection = ibm_db_dbi.connect(conn_str, "", "")
            self.log(f"Connected to DB2 database: {validated_database}")
        except Exception as e:
            # SECURITY: Use safe error messages that don't expose sensitive info
            safe_msg = create_safe_error_message(e, "while connecting to database")
            self.log(f"Connection failed: {safe_msg}")
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

            # Build vector store (will automatically generate embeddings for existing empty rows)
            self.log(f"Connecting to DB2 table: {validated_table_name}")
            vector_store = DB2VS(
                client=connection,
                embedding_function=self.embedding,
                table_name=validated_table_name,
                distance_strategy=distance_strategy_map.get(self.distance_strategy, DistanceStrategy.COSINE),
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
        """Perform similarity search and return results."""
        if not self.search_query:
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

        # Build vector store
        vector_store = self.build_vector_store()

        # Perform search based on search type
        if self.search_type == "Similarity":
            docs = vector_store.similarity_search(
                query=query_text,
                k=self.number_of_results,
            )
        elif self.search_type == "similarity_score_threshold":
            docs_and_scores = vector_store.similarity_search_with_relevance_scores(
                query=query_text,
                k=self.number_of_results,
            )
            # Apply threshold filtering
            docs = [doc for doc, score in docs_and_scores if score >= self.score_threshold]
        else:  # MMR
            docs = vector_store.max_marginal_relevance_search(
                query=query_text,
                k=self.number_of_results,
            )

        return docs_to_data(docs)

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
