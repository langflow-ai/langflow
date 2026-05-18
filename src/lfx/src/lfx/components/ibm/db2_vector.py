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
from lfx.inputs.inputs import BoolInput, DropdownInput, HandleInput, IntInput, SecretStrInput, StrInput
from lfx.io import Output, QueryInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class DB2VectorStoreComponent(LCVectorStoreComponent):
    """IBM Db2 Vector Store with search capabilities."""

    display_name: str = "IBM Db2 Vector Store"
    description: str = "IBM Db2 Vector Store with search capabilities"
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
            load_from_db=False,
            info="Name of the Db2 database",
        ),
        StrInput(
            name="hostname",
            display_name="Hostname",
            required=True,
            advanced=True,
            load_from_db=False,
            info="Db2 server hostname or IP address",
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
            load_from_db=False,
            info="Db2 database username",
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

            # Add documents if provided
            if self.ingest_data:
                import json

                import pandas as pd
                from langchain_core.documents import Document

                self.log(f"Starting data ingestion ({len(self.ingest_data)} items)")

                # OPTIMIZATION: Get existing document hashes if duplicate checking is enabled
                # Use hash-based comparison instead of fetching all text content
                stored_doc_hashes = set()
                if not self.allow_duplicates:
                    try:
                        import hashlib

                        cursor = connection.cursor()
                        # Only fetch text for hash comparison, more efficient than storing all text
                        query = f'SELECT {vector_store.column_names["text"]} FROM "{validated_table_name}"'  # noqa: S608
                        cursor.execute(query)
                        for row in cursor.fetchall():
                            if row[0]:
                                # Create hash of text content for efficient comparison
                                # Using MD5 for fast hashing of content (not for security)
                                text_hash = hashlib.md5(str(row[0]).encode()).hexdigest()  # noqa: S324
                                stored_doc_hashes.add(text_hash)
                        cursor.close()
                        self.log(f"Found {len(stored_doc_hashes)} existing documents")
                    except Exception:  # noqa: BLE001
                        self.log("Warning: Could not check for duplicates")

                documents = []
                for idx, data in enumerate(self.ingest_data):
                    # Reduced logging - only log every 100 items or first/last
                    if idx == 0 or idx == len(self.ingest_data) - 1 or (idx + 1) % 100 == 0:
                        self.log(f"Processing item {idx + 1}/{len(self.ingest_data)}")
                    if isinstance(data, Data):
                        doc = data.to_lc_document()
                        documents.append(doc)
                    elif isinstance(data, Document):
                        # Preserve existing metadata
                        documents.append(data)
                    elif isinstance(data, pd.DataFrame):
                        # Handle pandas DataFrame - extract metadata from columns
                        for _, row in data.iterrows():
                            # Separate text content from metadata fields
                            metadata = {}
                            text_parts = []

                            for col_name, val in row.items():
                                # Common metadata fields to extract
                                if col_name.lower() in ["brand", "category", "price", "product_id", "tenant_id", "id"]:
                                    if pd.notna(val):
                                        metadata[col_name] = val
                                elif col_name.lower() in ["description", "text", "content"]:
                                    # These are text content fields
                                    if pd.notna(val):
                                        text_parts.append(str(val))
                                else:
                                    # Other fields go to text
                                    try:
                                        if pd.notna(val):
                                            text_parts.append(str(val))
                                    except (ValueError, TypeError):
                                        text_parts.append(str(val))

                            text = " ".join(text_parts) if text_parts else ""
                            doc = Document(page_content=text, metadata=metadata)
                            documents.append(doc)
                    elif isinstance(data, pd.Series):
                        # Handle pandas Series - convert each value to a document
                        for val in data:
                            try:
                                if pd.notna(val):
                                    doc = Document(page_content=str(val), metadata={})
                                    documents.append(doc)
                            except (ValueError, TypeError):
                                doc = Document(page_content=str(val), metadata={})
                                documents.append(doc)
                    elif isinstance(data, dict):
                        # Handle JSON/dict objects - extract metadata intelligently
                        metadata = {}
                        text_content = None

                        # Extract known metadata fields
                        for key in ["brand", "category", "price", "product_id", "tenant_id", "id"]:
                            if key in data:
                                metadata[key] = data[key]

                        # Extract text content
                        if "description" in data:
                            text_content = data["description"]
                        elif "text" in data:
                            text_content = data["text"]
                        elif "content" in data:
                            text_content = data["content"]
                        else:
                            # Use entire dict as text if no specific text field
                            text_content = json.dumps(data)

                        doc = Document(page_content=text_content, metadata=metadata)
                        documents.append(doc)
                    elif hasattr(data, "text"):
                        # Handle Message or any object with text attribute
                        metadata = {}
                        if hasattr(data, "metadata"):
                            # Convert metadata to plain dict to ensure JSON serializability
                            if isinstance(data.metadata, dict):
                                metadata = dict(data.metadata)
                            elif hasattr(data.metadata, "__dict__"):
                                metadata = dict(data.metadata.__dict__)
                        doc = Document(page_content=data.text, metadata=metadata)
                        documents.append(doc)
                    elif isinstance(data, str):
                        # Check if it's CSV content
                        if "," in data and "\n" in data:
                            # Likely CSV - try to parse it
                            try:
                                import io

                                df = pd.read_csv(io.StringIO(data))
                                self.log(f"Detected CSV format with {len(df)} rows")

                                # Process as DataFrame
                                for _, row in df.iterrows():
                                    metadata = {}
                                    text_parts = []

                                    for col_name, val in row.items():
                                        if col_name.lower() in [
                                            "brand",
                                            "category",
                                            "price",
                                            "rating",
                                            "product_id",
                                            "tenant_id",
                                            "id",
                                        ]:
                                            if pd.notna(val):
                                                # Convert to Python native types for JSON serialization
                                                if isinstance(val, (pd.Int64Dtype, pd.Float64Dtype)):
                                                    metadata[col_name] = float(val)
                                                elif isinstance(val, (int, float)):
                                                    metadata[col_name] = val
                                                else:
                                                    metadata[col_name] = str(val)
                                        elif col_name.lower() in ["description", "text", "content"]:
                                            if pd.notna(val):
                                                text_parts.append(str(val))
                                        # Other fields go to text
                                        elif pd.notna(val):
                                            text_parts.append(str(val))

                                    text = " ".join(text_parts) if text_parts else ""
                                    doc = Document(page_content=text, metadata=metadata)
                                    documents.append(doc)
                            except (ValueError, pd.errors.ParserError) as e:
                                self.log(f"Failed to parse as CSV: {e}, treating as plain text")
                                doc = Document(page_content=data, metadata={})
                                documents.append(doc)
                        else:
                            # Handle plain strings
                            doc = Document(page_content=data, metadata={})
                            documents.append(doc)

                if documents:
                    self.log(f"Prepared {len(documents)} documents for ingestion")

                    # OPTIMIZATION: Filter out duplicates using hash-based comparison
                    if not self.allow_duplicates and stored_doc_hashes:
                        import hashlib

                        original_count = len(documents)
                        filtered_docs = []
                        for doc in documents:
                            # Using MD5 for fast hashing of content (not for security)
                            doc_hash = hashlib.md5(doc.page_content.encode()).hexdigest()  # noqa: S324
                            if doc_hash not in stored_doc_hashes:
                                filtered_docs.append(doc)
                        documents = filtered_docs
                        filtered_count = original_count - len(documents)
                        if filtered_count > 0:
                            self.log(f"Filtered out {filtered_count} duplicate documents")

                    if documents:
                        try:
                            self.log(f"Adding {len(documents)} documents to table '{validated_table_name}'")
                            vector_store.add_documents(documents)
                            self.log(f"Successfully ingested {len(documents)} documents")
                        except ValueError as e:
                            error_msg = str(e)
                            if "dimension mismatch" in error_msg.lower():
                                # Provide clear guidance on dimension mismatch
                                msg = (
                                    f"Embedding dimension mismatch detected. {error_msg}\n\n"
                                    f"To fix: Use a different table name or ensure your embedding model "
                                    f"produces the same dimension as the existing table."
                                )
                                raise ValueError(msg) from e
                            raise
                        except RuntimeError as e:
                            error_msg = str(e)
                            if "VECTOR" in error_msg and "cannot be CAST" in error_msg:
                                # DB2 vector dimension mismatch error
                                msg = (
                                    "DB2 vector dimension mismatch: The table was created with a different "
                                    "vector dimension. Use a different table name or recreate the table."
                                )
                                raise ValueError(msg) from e
                            # SECURITY: Use safe error messages
                            safe_msg = create_safe_error_message(e, "during document insertion")
                            raise RuntimeError(safe_msg) from e
                    else:
                        self.log("All documents were duplicates - skipped")
                else:
                    self.log("No documents to process")
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
