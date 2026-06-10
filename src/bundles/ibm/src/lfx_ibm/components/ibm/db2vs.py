from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import uuid
from collections.abc import Callable, Iterable
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    cast,
)

if TYPE_CHECKING:
    from ibm_db_dbi import Connection

import numpy as np
from langchain_community.vectorstores.utils import (
    DistanceStrategy,
    maximal_marginal_relevance,
)
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from lfx_ibm.components.ibm.db2_security import (
    create_safe_error_message,
    get_quoted_identifier,
    sanitize_sql_string,
    validate_identifier,
)

logger = logging.getLogger(__name__)
log_level = os.getenv("LOG_LEVEL", "WARNING").upper()  # Changed to WARNING for production
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger.setLevel(getattr(logging, log_level))


# Define a type variable that can be any kind of function
T = TypeVar("T", bound=Callable[..., Any])


def _handle_exceptions(func: T) -> T:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except RuntimeError as db_err:
            # Handle a known type of error (e.g., DB-related) specifically
            logger.exception("DB-related error occurred.")
            msg = f"Failed due to a DB issue: {db_err}"
            raise RuntimeError(msg) from db_err
        except ValueError as val_err:
            # Handle another known type of error specifically
            logger.exception("Validation error.")
            msg = f"Validation failed: {val_err}"
            raise ValueError(msg) from val_err
        except Exception as e:
            # Generic handler for all other exceptions
            logger.exception("An unexpected error occurred")
            msg = f"Unexpected error: {e}"
            raise RuntimeError(msg) from e

    return cast("T", wrapper)


def _quoted_table_identifier(table_name: str) -> str:
    """Return a double-quoted table identifier for validated table names."""
    return get_quoted_identifier(table_name)


def _table_exists(client: Connection, table_name: str) -> bool:
    quoted_table = _quoted_table_identifier(table_name)
    try:
        cursor = client.cursor()
        query = f"SELECT COUNT(*) FROM {quoted_table}"  # noqa: S608
        cursor.execute(query)
    except Exception as ex:
        if "SQL0204N" in str(ex):
            return False
        raise
    finally:
        cursor.close()
    return True


def _get_column_names(client: Connection, table_name: str) -> dict[str, str]:
    """Detect actual column names in the table (quoted or unquoted).

    Handles common column name variations:
    - 'text' can be 'TEXT', 'CONTENT', or 'text'
    - 'metadata' can be 'METADATA', 'META', or 'metadata'

    Returns a dict mapping logical names to actual column identifiers.
    For example: {'id': 'ID', 'text': 'CONTENT', 'metadata': 'META', 'embedding': 'EMBEDDING'}
    """
    cursor = client.cursor()
    try:
        # Query DB2 system catalog to get actual column names
        query = """
        SELECT COLNAME
        FROM SYSCAT.COLUMNS
        WHERE TABNAME = ?
        ORDER BY COLNO
        """
        cursor.execute(query, (table_name.upper(),))
        results = cursor.fetchall()

        if not results:
            # Table doesn't exist or no columns found, return quoted defaults
            return {"id": '"id"', "text": '"text"', "metadata": '"metadata"', "embedding": '"embedding"'}

        # Build a map of actual column names found in the table
        actual_columns = {}
        for row in results:
            col_name = row[0].strip()
            col_lower = col_name.lower()

            # Check if column is uppercase (unquoted) or mixed case (quoted)
            if col_name == col_name.upper():
                # Unquoted column - use without quotes
                actual_columns[col_lower] = col_name
            else:
                # Quoted column - use with quotes
                actual_columns[col_lower] = f'"{col_name}"'

        # Map logical names to actual column names with aliases
        column_map = {}

        # ID column
        column_map["id"] = actual_columns.get("id", actual_columns.get("_id", '"id"'))

        # TEXT column (can be 'text', 'content', 'data', etc.)
        column_map["text"] = actual_columns.get(
            "text", actual_columns.get("content", actual_columns.get("data", '"text"'))
        )

        # METADATA column (can be 'metadata', 'meta', 'properties', etc.)
        column_map["metadata"] = actual_columns.get(
            "metadata", actual_columns.get("meta", actual_columns.get("properties", '"metadata"'))
        )

        # EMBEDDING column
        column_map["embedding"] = actual_columns.get(
            "embedding", actual_columns.get("vector", actual_columns.get("embeddings", '"embedding"'))
        )

        logger.info("Column mapping for table %s: %s", table_name, column_map)
        return column_map
    finally:
        cursor.close()


def _get_distance_function(distance_strategy: DistanceStrategy) -> str:
    # Dictionary to map distance strategies to their corresponding function
    # names
    distance_strategy2function = {
        DistanceStrategy.EUCLIDEAN_DISTANCE: "EUCLIDEAN",
        DistanceStrategy.DOT_PRODUCT: "DOT",
        DistanceStrategy.COSINE: "COSINE",
    }

    # Attempt to return the corresponding distance function
    if distance_strategy in distance_strategy2function:
        return distance_strategy2function[distance_strategy]

    # If it's an unsupported distance strategy, raise an error
    msg = f"Unsupported distance strategy: {distance_strategy}"
    raise ValueError(msg)


@_handle_exceptions
def _create_table(client: Connection, table_name: str, embedding_dim: int) -> None:
    """Create a table for vector storage with validated table name.

    Args:
        client: Database connection
        table_name: Name of the table to create (will be validated)
        embedding_dim: Dimension of the embedding vectors

    Raises:
        ValueError: If table name is invalid
    """
    # Validate table name to prevent SQL injection
    validated_table_name = validate_identifier(table_name, "table name")

    cols_dict = {
        "id": "VARCHAR(100) PRIMARY KEY NOT NULL",
        "text": "CLOB(10M)",
        "metadata": "CLOB(1M)",
        "embedding": f"vector({embedding_dim}, FLOAT32)",
    }

    if not _table_exists(client, validated_table_name):
        cursor = client.cursor()
        try:
            ddl_body = ", ".join(f'"{col_name}" {col_type}' for col_name, col_type in cols_dict.items())
            # Use validated table name in query
            quoted_table = _quoted_table_identifier(validated_table_name)
            ddl = f"CREATE TABLE {quoted_table} ({ddl_body})"
            cursor.execute(ddl)
            cursor.execute("COMMIT")
            logger.debug("Table %s created successfully", validated_table_name)
        finally:
            cursor.close()
    else:
        logger.debug("Table %s already exists", validated_table_name)


@_handle_exceptions
def drop_table(client: Connection, table_name: str) -> None:
    """Drop a table from the database.

    Args:
        client: The ibm_db_dbi connection object.
        table_name: The name of the table to drop.

    Raises:
        RuntimeError: If an error occurs while dropping the table.
    """
    # Validate table name before using it in SQL
    validated_table_name = validate_identifier(table_name, "table name")
    quoted_table_name = _quoted_table_identifier(validated_table_name)

    if _table_exists(client, validated_table_name):
        cursor = client.cursor()
        ddl = f"DROP TABLE {quoted_table_name}"
        try:
            cursor.execute(ddl)
            cursor.execute("COMMIT")
            logger.info("Table %s dropped successfully...", validated_table_name)
        finally:
            cursor.close()
    else:
        logger.info("Table %s not found...", validated_table_name)


def _update_empty_embeddings(
    client: Connection,
    table_name: str,
    embedding_function: Callable[[str], list[float]] | Embeddings,
    column_names: dict[str, str],
) -> int:
    """Update rows that have NULL or empty embeddings.

    Args:
        client: The ibm_db_dbi connection object.
        table_name: The name of the table.
        embedding_function: Function to generate embeddings.
        column_names: Dictionary mapping logical column names to actual column names.

    Returns:
        Number of rows updated.
    """
    cursor = client.cursor()
    try:
        # Find rows with NULL or empty embeddings
        # Check for both NULL values and empty vectors
        query = f"""
        SELECT {column_names["id"]}, {column_names["text"]}
        FROM {_quoted_table_identifier(table_name)}
        WHERE {column_names["embedding"]} IS NULL
        """  # noqa: S608
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            logger.info("No rows with NULL embeddings found in %s", table_name)
            logger.info("Checking for rows with TEXT but no corresponding data...")

            # Also check if there are rows with text but we need to verify the table structure
            count_query = (
                f"SELECT COUNT(*) FROM {_quoted_table_identifier(table_name)} "  # noqa: S608
                f"WHERE {column_names['text']} IS NOT NULL"
            )
            cursor.execute(count_query)
            result = cursor.fetchone()
            total_rows = result[0] if result else 0
            logger.info("Total rows with text in table: %s", total_rows)

            if total_rows == 0:
                logger.info("No rows with text found in %s - table appears to be empty", table_name)

            return 0

        logger.info("Found %s rows with empty embeddings in %s", len(rows), table_name)

        # Generate embeddings for texts
        texts = [row[1] if row[1] is not None else "" for row in rows]
        ids = [row[0] for row in rows]

        # Generate embeddings
        if isinstance(embedding_function, Embeddings):
            embeddings = embedding_function.embed_documents(texts)
        elif callable(embedding_function):
            embeddings = [embedding_function(text) for text in texts]
        else:
            msg = "The embedding_function is neither Embeddings nor callable."
            raise TypeError(msg)

        # Get embedding dimension
        embedding_dim = len(embeddings[0]) if embeddings else 0

        # Update each row with its embedding
        update_query = f"""
        UPDATE {table_name}
        SET {column_names["embedding"]} = VECTOR(?, {embedding_dim}, FLOAT32)
        WHERE {column_names["id"]} = ?
        """  # noqa: S608

        update_data = [(f"{emb}", id_) for emb, id_ in zip(embeddings, ids, strict=False)]
        cursor.executemany(update_query, update_data)
        cursor.execute("COMMIT")

        logger.info("Successfully updated %s rows with embeddings", len(rows))
        return len(rows)

    except Exception:
        logger.exception("Error updating empty embeddings")
        cursor.execute("ROLLBACK")
        raise
    finally:
        cursor.close()


class DB2VS(VectorStore):
    """`DB2VS` vector store.

    To use, you should have:
    - the ``ibm_db`` python package installed
    - a connection to db2 database with vector store feature (v12.1.2+)
    """

    def __init__(
        self,
        client: Connection,
        embedding_function: Callable[[str], list[float]] | Embeddings,
        table_name: str,
        distance_strategy: DistanceStrategy = DistanceStrategy.EUCLIDEAN_DISTANCE,
        query: str | None = "What is a Db2 database",
        params: dict[str, Any] | None = None,
        use_bulk_insert: bool = True,  # noqa: FBT001, FBT002
    ):
        """Initialize DB2 vector store with security validations.

        Args:
            client: IBM DB2 database connection
            embedding_function: Function or Embeddings object to generate embeddings
            table_name: Name of the table to store vectors (will be validated)
            distance_strategy: Strategy for distance calculation
            query: Optional default query
            params: Optional additional parameters
            use_bulk_insert: Enable bulk insert using executemany() for better performance (default: True)

        Raises:
            ValueError: If table name is invalid or other validation fails
            RuntimeError: If database operations fail
        """
        # Imported lazily because ibm-db ships no linux/aarch64 wheel (see the
        # platform marker in this bundle's pyproject.toml).  Keeping it out of
        # module import lets the bundle load on that arch even though this
        # vector store cannot run there.  Mirrors db2_vector.build_vector_store.
        import ibm_db_dbi

        try:
            # SECURITY: Validate table name before any operations
            validated_table_name = validate_identifier(table_name, "table name")

            self.client = client
            self.table_name = validated_table_name
            self.use_bulk_insert = use_bulk_insert

            if not isinstance(embedding_function, Embeddings):
                logger.warning(
                    "`embedding_function` is expected to be an Embeddings "
                    "object, support for passing in a function will soon "
                    "be removed."
                )
            self.embedding_function = embedding_function
            self.query = query
            self.distance_strategy = distance_strategy
            self.params = params

            # Get embedding dimension
            embedding_dim = self.get_embedding_dimension()

            # Check if table exists before creating
            table_existed = _table_exists(client, validated_table_name)
            _create_table(client, validated_table_name, embedding_dim)

            # Detect actual column names (quoted or unquoted)
            self.column_names = _get_column_names(client, validated_table_name)
            logger.debug("Detected column names: %s", self.column_names)

            # If table already existed, check for and update rows with empty embeddings
            if table_existed:
                logger.debug("Table %s exists - checking for empty embeddings", validated_table_name)
                try:
                    updated_count = _update_empty_embeddings(
                        client, validated_table_name, embedding_function, self.column_names
                    )
                    if updated_count > 0:
                        logger.info("Updated %s rows with embeddings", updated_count)
                    else:
                        logger.debug("No empty embeddings found in %s", validated_table_name)
                except Exception:
                    logger.exception("Could not update empty embeddings")
                    raise
        except ValueError:
            # Validation errors (e.g., invalid table name)
            logger.exception("Validation error")
            raise
        except ibm_db_dbi.DatabaseError as db_err:
            # Database-specific errors
            safe_msg = create_safe_error_message(db_err, "while initializing vector store")
            logger.exception(safe_msg)
            raise RuntimeError(safe_msg) from db_err
        except Exception as ex:
            # Unexpected errors
            safe_msg = create_safe_error_message(ex, "while initializing vector store")
            logger.exception(safe_msg)
            raise RuntimeError(safe_msg) from ex

    @property
    def embeddings(self) -> Embeddings | None:
        """A property that returns an Embeddings instance if embedding_function is an instance of Embeddings.

        Otherwise returns None.

        Returns:
            Optional[Embeddings]: Embeddings instance if embedding_function
            is an instance of Embeddings, otherwise returns None.
        """
        return self.embedding_function if isinstance(self.embedding_function, Embeddings) else None

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings from the embedding function."""
        # Embed the single document by wrapping it in a list
        embedded_document = self._embed_documents([self.query if self.query is not None else ""])

        # Get the first (and only) embedding's dimension
        return len(embedded_document[0])

    def _validate_embedding_dimension(self, embeddings: list[list[float]]) -> None:
        """Validate that embeddings match the table's vector dimension.

        Args:
            embeddings: List of embedding vectors to validate

        Raises:
            ValueError: If embedding dimensions don't match table dimension
        """
        if not embeddings:
            return

        actual_dim = len(embeddings[0])
        expected_dim = self.get_embedding_dimension()

        if actual_dim != expected_dim:
            msg = (
                f"Embedding dimension mismatch: expected {expected_dim}, "
                f"got {actual_dim}. The table '{self.table_name}' was created "
                f"with dimension {expected_dim}. Either drop the table using "
                f"drop_table() or use an embedding model with {expected_dim} dimensions."
            )
            raise ValueError(msg)

    def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        if isinstance(self.embedding_function, Embeddings):
            return self.embedding_function.embed_documents(texts)
        if callable(self.embedding_function):
            return [self.embedding_function(text) for text in texts]
        msg = "The embedding_function is neither Embeddings nor callable."
        raise TypeError(msg)

    def _embed_query(self, text: str) -> list[float]:
        if isinstance(self.embedding_function, Embeddings):
            return self.embedding_function.embed_query(text)
        return self.embedding_function(text)

    @_handle_exceptions
    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: list[dict[Any, Any]] | None = None,
        ids: list[str] | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> list[str]:
        """Add more texts to the vectorstore.

        Args:
            texts: Iterable of strings to add to the vectorstore.
            metadatas: Optional list of metadatas associated with the texts.
            ids: Optional list of ids for the texts that are being added to the vector store.
            kwargs: vectorstore specific parameters

        Returns:
            List of ids from adding the texts into the vectorstore.

        Raises:
            ValueError: If inputs are invalid or embedding dimensions don't match
        """
        texts = list(texts)

        if metadatas and len(metadatas) != len(texts):
            msg = f"metadatas must be the same length as texts. Got {len(metadatas)} metadatas and {len(texts)} texts."
            raise ValueError(msg)

        if ids:
            if len(ids) != len(texts):
                msg = f"ids must be the same length as texts. Got {len(ids)} ids and {len(texts)} texts."
                raise ValueError(msg)
            # Use actual IDs directly (validated for length)
            processed_ids = [str(_id)[:100] for _id in ids]  # Limit to VARCHAR(100)
        elif metadatas:
            if all("id" in metadata for metadata in metadatas):
                # Use actual IDs from metadata
                processed_ids = [str(metadata["id"])[:100] for metadata in metadatas]
            else:
                # In the case partial metadata has id, use actual id if available
                processed_ids = []
                for metadata in metadatas:
                    if "id" in metadata:
                        processed_ids.append(str(metadata["id"])[:100])
                    else:
                        # Only generate ID if not provided
                        processed_ids.append(hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:16].upper())
        else:
            # Generate new ids if none are provided
            generated_ids = [str(uuid.uuid4()) for _ in texts]
            processed_ids = [hashlib.sha256(_id.encode()).hexdigest()[:16].upper() for _id in generated_ids]

        if not texts:
            return []

        # Generate embeddings
        embeddings = self._embed_documents(texts)

        # CRITICAL: Validate embedding dimensions before insert
        self._validate_embedding_dimension(embeddings)

        if not metadatas:
            metadatas = [{} for _ in texts]

        embedding_len = self.get_embedding_dimension()

        cursor = self.client.cursor()
        try:
            if self.use_bulk_insert:
                # BULK INSERT MODE: Use executemany() for better performance
                logger.debug("Using BULK INSERT mode (executemany) for %s documents", len(processed_ids))

                # Build the SQL statement with placeholders for bulk insert
                sql_insert = f"""
                INSERT INTO {_quoted_table_identifier(self.table_name)}
                ({self.column_names["id"]}, {self.column_names["embedding"]},
                 {self.column_names["metadata"]}, {self.column_names["text"]})
                VALUES (?, VECTOR(?, {embedding_len}, FLOAT32), ?, ?)
                """  # noqa: S608

                # Prepare data tuples for executemany
                insert_data = []
                for id_, embedding, metadata, text in zip(processed_ids, embeddings, metadatas, texts, strict=False):
                    # Convert numpy array to Python list if needed
                    embedding_list = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)

                    # Format as string for VECTOR() function
                    vector_str = str(embedding_list)

                    metadata_json = json.dumps(metadata)

                    insert_data.append((id_, vector_str, metadata_json, text or ""))

                # Use executemany for bulk insert - much more efficient
                cursor.executemany(sql_insert, insert_data)
                logger.debug("Successfully inserted %s documents using bulk insert", len(processed_ids))

            else:
                # ROW-BY-ROW INSERT MODE: Use execute() for each row (for debugging/compatibility)
                logger.debug("Using ROW-BY-ROW INSERT mode (execute) for %s documents", len(processed_ids))

                for idx, (id_, embedding, metadata, text) in enumerate(
                    zip(processed_ids, embeddings, metadatas, texts, strict=False), 1
                ):
                    # Convert numpy array to Python list if needed
                    embedding_list = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)

                    # Format as string for VECTOR() function
                    vector_str = str(embedding_list)

                    # SECURITY: Properly sanitize text using SQL-safe escaping
                    text_sanitized = sanitize_sql_string(text) if text else ""

                    # SECURITY: Sanitize metadata JSON
                    metadata_json = json.dumps(metadata)
                    metadata_sanitized = sanitize_sql_string(metadata_json)

                    # SECURITY: Sanitize ID (already limited to 100 chars)
                    id_sanitized = sanitize_sql_string(id_)

                    # Build SQL with sanitized values
                    sql_insert = f"""
                    INSERT INTO {_quoted_table_identifier(self.table_name)}
                    ({self.column_names["id"]}, {self.column_names["embedding"]},
                     {self.column_names["metadata"]}, {self.column_names["text"]})
                    VALUES ('{id_sanitized}', VECTOR('{vector_str}', {embedding_len}, FLOAT32),
                            '{metadata_sanitized}', '{text_sanitized}')
                    """  # noqa: S608

                    # Log progress for first insert
                    if idx == 1:
                        logger.debug("Inserting documents 1-%s into %s", len(processed_ids), self.table_name)

                    # Execute the insert for this row
                    cursor.execute(sql_insert)

                logger.debug("Successfully inserted %s documents using row-by-row insert", len(processed_ids))

            cursor.execute("COMMIT")
        except Exception as e:
            # Rollback on error
            import contextlib

            with contextlib.suppress(Exception):
                cursor.execute("ROLLBACK")
            # Create safe error message
            safe_msg = create_safe_error_message(e, "during document insertion")
            raise RuntimeError(safe_msg) from e
        finally:
            cursor.close()
        return processed_ids

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,  # noqa: A002
        **kwargs: Any,
    ) -> list[Document]:
        """Return docs most similar to query.

        Args:
            query: str,
            k: int, the number for documents to retrieve
            filter: Optional, the filter to apply
            **kwargs: Additional keyword arguments
        Return:
            List[Document]: documents most similar to a query
        """
        embedding = self._embed_query(query)
        return self.similarity_search_by_vector(embedding=embedding, k=k, filter=filter, **kwargs)

    def similarity_search_by_vector(
        self,
        embedding: list[float],
        k: int = 4,
        filter: dict[str, Any] | None = None,  # noqa: A002
        **kwargs: Any,
    ) -> list[Document]:
        docs_and_scores = self.similarity_search_by_vector_with_relevance_scores(
            embedding=embedding, k=k, filter=filter, **kwargs
        )
        return [doc for doc, _ in docs_and_scores]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,  # noqa: A002
        **kwargs: Any,
    ) -> list[tuple[Document, float]]:
        """Return docs most similar to query.

        Args:
            query: Query string
            k: Number of documents to return
            filter: Optional filter
            **kwargs: Additional keyword arguments

        Returns:
            List of (Document, score) tuples
        """
        embedding = (
            self.embedding_function.embed_query(query)
            if isinstance(self.embedding_function, Embeddings)
            else self._embed_query(query)
        )
        return self.similarity_search_by_vector_with_relevance_scores(embedding=embedding, k=k, filter=filter, **kwargs)

    @_handle_exceptions
    def similarity_search_by_vector_with_relevance_scores(
        self,
        embedding: list[float],
        k: int = 4,
        filter: dict[str, Any] | None = None,  # noqa: A002
        **kwargs: Any,  # noqa: ARG002
    ) -> list[tuple[Document, float]]:
        docs_and_scores = []
        embedding_len = self.get_embedding_dimension()

        query = f"""
        SELECT {self.column_names["id"]},
          {self.column_names["text"]},
          {self.column_names["metadata"]},
          vector_distance({self.column_names["embedding"]}, VECTOR('{embedding}', {embedding_len}, FLOAT32),
          {_get_distance_function(self.distance_strategy)}) as distance
        FROM {_quoted_table_identifier(self.table_name)}
        ORDER BY distance
        FETCH FIRST {k} ROWS ONLY
        """  # noqa: S608
        # TODO: No APPROX in "FETCH APPROX FIRST" now. This will be added once
        # approximate nearest neighbors search in db2 is implemented.

        # Log the query with truncated embedding
        embedding_preview = str(embedding[:3]) + "..." + str(embedding[-3:])
        query_preview = f"""
        SELECT {self.column_names["id"]},
          {self.column_names["text"]},
          {self.column_names["metadata"]},
          vector_distance({self.column_names["embedding"]}, VECTOR('[{embedding_preview}]', {embedding_len}, FLOAT32),
          {_get_distance_function(self.distance_strategy)}) as distance
        FROM {_quoted_table_identifier(self.table_name)}
        ORDER BY distance
        FETCH FIRST {k} ROWS ONLY
        """  # noqa: S608
        logger.info("🔍 Executing similarity search query:")
        logger.info("   Table: %s", self.table_name)
        logger.info("   Distance strategy: %s", _get_distance_function(self.distance_strategy))
        logger.info("   Top K: %s", k)
        logger.info("   SQL: %s", query_preview.strip())

        # Execute the query
        cursor = self.client.cursor()
        try:
            cursor.execute(query)
            results = cursor.fetchall()
            logger.info("✅ Retrieved %s results", len(results))

            # Filter results if filter is provided
            for result in results:
                # Handle metadata - convert memoryview/bytes to string if needed
                meta_raw = result[2]
                if meta_raw is None:
                    metadata = {}
                elif isinstance(meta_raw, (bytes, memoryview)):
                    metadata = json.loads(bytes(meta_raw).decode("utf-8"))
                elif isinstance(meta_raw, str):
                    metadata = json.loads(meta_raw)
                else:
                    metadata = {}

                # Apply filtering based on the 'filter' dictionary
                if filter:
                    if all(metadata.get(key) in value for key, value in filter.items()):
                        doc = Document(
                            page_content=(result[1] if result[1] is not None else ""),
                            metadata=metadata,
                        )
                        distance = result[3]
                        docs_and_scores.append((doc, distance))
                else:
                    doc = Document(
                        page_content=(result[1] if result[1] is not None else ""),
                        metadata=metadata,
                    )
                    distance = result[3]
                    docs_and_scores.append((doc, distance))
        finally:
            cursor.close()
        return docs_and_scores

    @_handle_exceptions
    def similarity_search_by_vector_returning_embeddings(
        self,
        embedding: list[float],
        k: int,
        filter: dict[str, Any] | None = None,  # noqa: A002
        **kwargs: Any,  # noqa: ARG002
    ) -> list[tuple[Document, float, np.ndarray]]:
        documents = []
        embedding_len = self.get_embedding_dimension()

        query = f"""
        SELECT {self.column_names["id"]},
          {self.column_names["text"]},
          {self.column_names["metadata"]},
          vector_distance({self.column_names["embedding"]}, VECTOR('{embedding}', {embedding_len}, FLOAT32),
          {_get_distance_function(self.distance_strategy)}) as distance,
          {self.column_names["embedding"]}
        FROM {_quoted_table_identifier(self.table_name)}
        ORDER BY distance
        FETCH FIRST {k} ROWS ONLY
        """  # noqa: S608
        # TODO: No APPROX in "FETCH APPROX FIRST" now. This will be added once
        # approximate nearest neighbors search in db2 is implemented.

        # Execute the query
        cursor = self.client.cursor()
        try:
            cursor.execute(query)
            results = cursor.fetchall()

            for result in results:
                page_content_str = result[1] if result[1] is not None else ""

                # Handle metadata - convert memoryview/bytes to string if needed
                meta_raw = result[2]
                if meta_raw is None:
                    metadata = {}
                elif isinstance(meta_raw, (bytes, memoryview)):
                    metadata = json.loads(bytes(meta_raw).decode("utf-8"))
                elif isinstance(meta_raw, str):
                    metadata = json.loads(meta_raw)
                else:
                    metadata = {}

                # Apply filter if provided and matches; otherwise, add all
                # documents
                if not filter or all(metadata.get(key) in value for key, value in filter.items()):
                    document = Document(page_content=page_content_str, metadata=metadata)
                    distance = result[3]

                    # Assuming result[4] is already in the correct format;
                    # adjust if necessary
                    current_embedding = (
                        np.array(json.loads(result[4]), dtype=np.float32)
                        if result[4]
                        else np.empty(0, dtype=np.float32)
                    )

                    documents.append((document, distance, current_embedding))
        finally:
            cursor.close()
        return documents  # type: ignore[return-value]

    @_handle_exceptions
    def max_marginal_relevance_search_with_score_by_vector(
        self,
        embedding: list[float],
        *,
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: dict[str, Any] | None = None,  # noqa: A002
    ) -> list[tuple[Document, float]]:
        """Return docs and their similarity scores selected using the maximal marginal relevance.

        Maximal marginal relevance optimizes for similarity to query AND
        diversity among selected documents.

        Args:
          self: An instance of the class
          embedding: Embedding to look up documents similar to.
          k: Number of Documents to return. The default value is 4.
          fetch_k: Number of Documents to fetch before filtering to
                   pass to MMR algorithm.
          filter: (Optional[Dict[str, str]]): Filter by metadata. Defaults
          to None.
          lambda_mult: Number between 0 and 1 that determines the degree
                       of diversity among the results with 0 corresponding
                       to maximum diversity and 1 to minimum diversity.
                       The default value is 0.5.

        Returns:
            List of Documents and similarity scores selected by maximal
            marginal relevance and score for each.
        """
        # Fetch documents and their scores
        docs_scores_embeddings = self.similarity_search_by_vector_returning_embeddings(
            embedding, fetch_k, filter=filter
        )
        # Assuming documents_with_scores is a list of tuples (Document, score)

        # If you need to split documents and scores for processing (e.g.,
        # for MMR calculation)
        documents, scores, embeddings = (
            zip(*docs_scores_embeddings, strict=False) if docs_scores_embeddings else ([], [], [])
        )

        # Assume maximal_marginal_relevance method accepts embeddings and
        # scores, and returns indices of selected docs
        mmr_selected_indices = maximal_marginal_relevance(
            np.array(embedding, dtype=np.float32),
            list(embeddings),
            k=k,
            lambda_mult=lambda_mult,
        )

        # Filter documents based on MMR-selected indices and map scores
        return [(documents[i], scores[i]) for i in mmr_selected_indices]

    @_handle_exceptions
    def max_marginal_relevance_search_by_vector(
        self,
        embedding: list[float],
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: dict[str, Any] | None = None,  # noqa: A002
        **kwargs: Any,  # noqa: ARG002
    ) -> list[Document]:
        """Return docs selected using the maximal marginal relevance.

        Maximal marginal relevance optimizes for similarity to query AND
        diversity among selected documents.

        Args:
          self: An instance of the class
          embedding: Embedding to look up documents similar to.
          k: Number of Documents to return. Defaults to 4.
          fetch_k: Number of Documents to fetch to pass to MMR algorithm.
          lambda_mult: Number between 0 and 1 that determines the degree
                       of diversity among the results with 0 corresponding
                       to maximum diversity and 1 to minimum diversity.
                       Defaults to 0.5.
          filter: Optional[Dict[str, Any]]
          **kwargs: Any
        Returns:
          List of Documents selected by maximal marginal relevance.
        """
        docs_and_scores = self.max_marginal_relevance_search_with_score_by_vector(
            embedding, k=k, fetch_k=fetch_k, lambda_mult=lambda_mult, filter=filter
        )
        return [doc for doc, _ in docs_and_scores]

    @_handle_exceptions
    def max_marginal_relevance_search(
        self,
        query: str,
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: dict[str, Any] | None = None,  # noqa: A002
        **kwargs: Any,
    ) -> list[Document]:
        """Return docs selected using the maximal marginal relevance.

        Args:
            query: Query string
            k: Number of documents to return
            fetch_k: Number of documents to fetch before filtering
            lambda_mult: Diversity parameter (0=max diversity, 1=min diversity)
            filter: Optional metadata filter
            **kwargs: Additional keyword arguments

        Returns:
            List of Documents
        """
        """Return docs selected using the maximal marginal relevance.

        Maximal marginal relevance optimizes for similarity to query AND
        diversity among selected documents.

        Args:
          self: An instance of the class
          query: Text to look up documents similar to.
          k: Number of Documents to return. The default value is 4.
          fetch_k: Number of Documents to fetch to pass to MMR algorithm.
          lambda_mult: Number between 0 and 1 that determines the degree
                       of diversity among the results with 0 corresponding
                       to maximum diversity and 1 to minimum diversity.
                       The default value is 0.5.
          filter: Optional[Dict[str, Any]]
          **kwargs
        Returns:
          List of Documents selected by maximal marginal relevance.

        `max_marginal_relevance_search` requires that `query` returns matched
        embeddings alongside the match documents.
        """
        embedding = self._embed_query(query)
        return self.max_marginal_relevance_search_by_vector(
            embedding=embedding,
            k=k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult,
            filter=filter,
            **kwargs,
        )

    @_handle_exceptions
    def delete(self, ids: list[str] | None = None, **kwargs: Any) -> None:  # noqa: ARG002
        """Delete by vector IDs.

        Args:
            ids: List of IDs to delete
            **kwargs: Additional keyword arguments (unused)

        Args:
          self: An instance of the class
          ids: List of ids to delete (already hashed from add_texts).
          **kwargs
        """
        if ids is None:
            msg = "No ids provided to delete."
            raise ValueError(msg)

        # IDs are already hashed and truncated from add_texts, use them directly
        # Normalize to uppercase to match the format used in add_texts
        normalized_ids = [_id.upper()[:16] for _id in ids]

        # Constructing the SQL statement with individual placeholders
        placeholders = ", ".join(["?" for _ in range(len(normalized_ids))])

        ddl = (
            f"DELETE FROM {_quoted_table_identifier(self.table_name)} "  # noqa: S608
            f"WHERE {self.column_names['id']} IN ({placeholders})"
        )
        cursor = self.client.cursor()
        try:
            cursor.execute(ddl, normalized_ids)
            cursor.execute("COMMIT")
        finally:
            cursor.close()

    def update_empty_embeddings(self) -> int:
        """Update rows in the table that have NULL or empty embeddings.

        This method is useful when you have an existing table with data but
        empty embedding columns. It will:
        1. Find all rows where the embedding column is NULL
        2. Generate embeddings for the text in those rows
        3. Update the rows with the generated embeddings

        Returns:
            int: Number of rows that were updated with embeddings

        Example:
            >>> vector_store = DB2VS(...)
            >>> updated_count = vector_store.update_empty_embeddings()
            >>> print(f"Updated {updated_count} rows with embeddings")
        """
        return _update_empty_embeddings(self.client, self.table_name, self.embedding_function, self.column_names)

    @classmethod
    @_handle_exceptions
    def from_texts(
        cls: type[DB2VS],
        texts: Iterable[str],
        embedding: Embeddings,
        metadatas: list[dict] | None = None,
        **kwargs: Any,
    ) -> DB2VS:
        """Return VectorStore initialized from texts and embeddings."""
        client = kwargs.get("client")
        if client is None:
            msg = "client parameter is required..."
            raise ValueError(msg)
        params = kwargs.get("params", {})

        table_name = str(kwargs.get("table_name", "langchain"))

        # Get distance_strategy with default
        distance_strategy = kwargs.get("distance_strategy", DistanceStrategy.COSINE)
        if not isinstance(distance_strategy, DistanceStrategy):
            msg = f"Expected DistanceStrategy got {type(distance_strategy).__name__}"
            raise TypeError(msg)

        query = kwargs.get("query", "What is a Db2 database")

        drop_table(client, table_name)

        vss = cls(
            client=client,
            embedding_function=embedding,
            table_name=table_name,
            distance_strategy=distance_strategy,
            query=query,
            params=params,
        )
        vss.add_texts(texts=list(texts), metadatas=metadatas)
        return vss
