from __future__ import annotations

import copy
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import OpenSearchException, RequestError

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MultilineInput, SecretStrInput, StrInput, TableInput
from lfx.log import logger
from lfx.schema.data import Data


def normalize_model_name(model_name: str) -> str:
    """Normalize embedding model name for use as field suffix.

    Converts model names to valid OpenSearch field names by replacing
    special characters and ensuring alphanumeric format.

    Args:
        model_name: Original embedding model name (e.g., "text-embedding-3-small")

    Returns:
        Normalized field suffix (e.g., "text_embedding_3_small")
    """
    normalized = model_name.lower()
    # Replace common separators with underscores
    normalized = normalized.replace("-", "_").replace(":", "_").replace("/", "_").replace(".", "_")
    # Remove any non-alphanumeric characters except underscores
    normalized = "".join(c if c.isalnum() or c == "_" else "_" for c in normalized)
    # Remove duplicate underscores
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def get_embedding_field_name(model_name: str) -> str:
    """Get the dynamic embedding field name for a model.

    Args:
        model_name: Embedding model name

    Returns:
        Field name in format: chunk_embedding_{normalized_model_name}
    """
    logger.info(f"chunk_embedding_{normalize_model_name(model_name)}")
    return f"chunk_embedding_{normalize_model_name(model_name)}"


@vector_store_connection
class OpenSearchVectorStoreComponentMultimodalMultiEmbedding(LCVectorStoreComponent):
    """OpenSearch Vector Store Component with Multi-Model Hybrid Search Capabilities.

    This component provides vector storage and retrieval using OpenSearch, combining semantic
    similarity search (KNN) with keyword-based search for optimal results. It supports:
    - Multiple embedding models per index with dynamic field names
    - Automatic detection and querying of all available embedding models
    - Parallel embedding generation for multi-model search
    - Document ingestion with model tracking
    - Advanced filtering and aggregations
    - Flexible authentication options

    Features:
    - Multi-model vector storage with dynamic fields (chunk_embedding_{model_name})
    - Hybrid search combining multiple KNN queries (dis_max) + keyword matching
    - Auto-detection of available models in the index
    - Parallel query embedding generation for all detected models
    - Vector storage with configurable engines (jvector, nmslib, faiss, lucene)
    - Flexible authentication (Basic auth, JWT tokens)

    Model Name Resolution:
    - Priority: deployment > model > model_name attributes
    - This ensures correct matching between embedding objects and index fields
    - When multiple embeddings are provided, specify embedding_model_name to select which one to use
    - During search, each detected model in the index is matched to its corresponding embedding object
    """

    display_name: str = "OpenSearch (Multi-Model Multi-Embedding)"
    icon: str = "OpenSearch"
    description: str = (
        "Store and search documents using OpenSearch with multi-model hybrid semantic and keyword search."
    )

    # Keys we consider baseline
    default_keys: list[str] = [
        "opensearch_url",
        "index_name",
        *[i.name for i in LCVectorStoreComponent.inputs],  # search_query, add_documents, etc.
        "embedding",
        "embedding_model_name",
        "vector_field",
        "number_of_results",
        "auth_mode",
        "username",
        "password",
        "jwt_token",
        "jwt_header",
        "bearer_prefix",
        "use_ssl",
        "verify_certs",
        "filter_expression",
        "engine",
        "space_type",
        "ef_construction",
        "m",
        "num_candidates",
        "docs_metadata",
    ]

    inputs = [
        TableInput(
            name="docs_metadata",
            display_name="Document Metadata",
            info=(
                "Additional metadata key-value pairs to be added to all ingested documents. "
                "Useful for tagging documents with source information, categories, or other custom attributes."
            ),
            table_schema=[
                {
                    "name": "key",
                    "display_name": "Key",
                    "type": "str",
                    "description": "Key name",
                },
                {
                    "name": "value",
                    "display_name": "Value",
                    "type": "str",
                    "description": "Value of the metadata",
                },
            ],
            value=[],
            input_types=["Data"],
        ),
        StrInput(
            name="opensearch_url",
            display_name="OpenSearch URL",
            value="http://localhost:9200",
            info=(
                "The connection URL for your OpenSearch cluster "
                "(e.g., http://localhost:9200 for local development or your cloud endpoint)."
            ),
        ),
        StrInput(
            name="index_name",
            display_name="Index Name",
            value="langflow",
            info=(
                "The OpenSearch index name where documents will be stored and searched. "
                "Will be created automatically if it doesn't exist."
            ),
        ),
        DropdownInput(
            name="engine",
            display_name="Vector Engine",
            options=["jvector", "nmslib", "faiss", "lucene"],
            value="jvector",
            info=(
                "Vector search engine for similarity calculations. 'jvector' is recommended for most use cases. "
                "Note: Amazon OpenSearch Serverless only supports 'nmslib' or 'faiss'."
            ),
            advanced=True,
        ),
        DropdownInput(
            name="space_type",
            display_name="Distance Metric",
            options=["l2", "l1", "cosinesimil", "linf", "innerproduct"],
            value="l2",
            info=(
                "Distance metric for calculating vector similarity. 'l2' (Euclidean) is most common, "
                "'cosinesimil' for cosine similarity, 'innerproduct' for dot product."
            ),
            advanced=True,
        ),
        IntInput(
            name="ef_construction",
            display_name="EF Construction",
            value=512,
            info=(
                "Size of the dynamic candidate list during index construction. "
                "Higher values improve recall but increase indexing time and memory usage."
            ),
            advanced=True,
        ),
        IntInput(
            name="m",
            display_name="M Parameter",
            value=16,
            info=(
                "Number of bidirectional connections for each vector in the HNSW graph. "
                "Higher values improve search quality but increase memory usage and indexing time."
            ),
            advanced=True,
        ),
        IntInput(
            name="num_candidates",
            display_name="Candidate Pool Size",
            value=1000,
            info=(
                "Number of approximate neighbors to consider for each KNN query. "
                "Some OpenSearch deployments do not support this parameter; set to 0 to disable."
            ),
            advanced=True,
        ),
        *LCVectorStoreComponent.inputs,  # includes search_query, add_documents, etc.
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"], is_list=True),
        StrInput(
            name="embedding_model_name",
            display_name="Embedding Model Name",
            value="",
            info=(
                "Name of the embedding model to use for ingestion. This selects which embedding from the list "
                "will be used to embed documents. Matches on deployment, model, model_id, or model_name. "
                "For duplicate deployments, use combined format: 'deployment:model' "
                "(e.g., 'text-embedding-ada-002:text-embedding-3-large'). "
                "Leave empty to use the first embedding. Error message will show all available identifiers."
            ),
            advanced=False,
        ),
        StrInput(
            name="vector_field",
            display_name="Legacy Vector Field Name",
            value="chunk_embedding",
            advanced=True,
            info=(
                "Legacy field name for backward compatibility. New documents use dynamic fields "
                "(chunk_embedding_{model_name}) based on the embedding_model_name."
            ),
        ),
        IntInput(
            name="number_of_results",
            display_name="Default Result Limit",
            value=10,
            advanced=True,
            info=(
                "Default maximum number of search results to return when no limit is "
                "specified in the filter expression."
            ),
        ),
        MultilineInput(
            name="filter_expression",
            display_name="Search Filters (JSON)",
            value="",
            info=(
                "Optional JSON configuration for search filtering, result limits, and score thresholds.\n\n"
                "Format 1 - Explicit filters:\n"
                '{"filter": [{"term": {"filename":"doc.pdf"}}, '
                '{"terms":{"owner":["user1","user2"]}}], "limit": 10, "score_threshold": 1.6}\n\n'
                "Format 2 - Context-style mapping:\n"
                '{"data_sources":["file.pdf"], "document_types":["application/pdf"], "owners":["user123"]}\n\n'
                "Use __IMPOSSIBLE_VALUE__ as placeholder to ignore specific filters."
            ),
        ),
        # ----- Auth controls (dynamic) -----
        DropdownInput(
            name="auth_mode",
            display_name="Authentication Mode",
            value="basic",
            options=["basic", "jwt"],
            info=(
                "Authentication method: 'basic' for username/password authentication, "
                "or 'jwt' for JSON Web Token (Bearer) authentication."
            ),
            real_time_refresh=True,
            advanced=False,
        ),
        StrInput(
            name="username",
            display_name="Username",
            value="admin",
            show=True,
        ),
        SecretStrInput(
            name="password",
            display_name="OpenSearch Password",
            value="admin",
            show=True,
        ),
        SecretStrInput(
            name="jwt_token",
            display_name="JWT Token",
            value="JWT",
            load_from_db=False,
            show=False,
            info=(
                "Valid JSON Web Token for authentication. "
                "Will be sent in the Authorization header (with optional 'Bearer ' prefix)."
            ),
        ),
        StrInput(
            name="jwt_header",
            display_name="JWT Header Name",
            value="Authorization",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="bearer_prefix",
            display_name="Prefix 'Bearer '",
            value=True,
            show=False,
            advanced=True,
        ),
        # ----- TLS -----
        BoolInput(
            name="use_ssl",
            display_name="Use SSL/TLS",
            value=True,
            advanced=True,
            info="Enable SSL/TLS encryption for secure connections to OpenSearch.",
        ),
        BoolInput(
            name="verify_certs",
            display_name="Verify SSL Certificates",
            value=False,
            advanced=True,
            info=(
                "Verify SSL certificates when connecting. "
                "Disable for self-signed certificates in development environments."
            ),
        ),
    ]

    def _get_embedding_model_name(self, embedding_obj=None) -> str:
        """Get the embedding model name from component config or embedding object.

        Priority: deployment > model > model_id > model_name
        This ensures we use the actual model being deployed, not just the configured model.
        Supports multiple embedding providers (OpenAI, Watsonx, Cohere, etc.)

        Args:
            embedding_obj: Specific embedding object to get name from (optional)

        Returns:
            Embedding model name

        Raises:
            ValueError: If embedding model name cannot be determined
        """
        # First try explicit embedding_model_name input
        if hasattr(self, "embedding_model_name") and self.embedding_model_name:
            return self.embedding_model_name.strip()

        # Try to get from provided embedding object
        if embedding_obj:
            # Priority: deployment > model > model_id > model_name
            if hasattr(embedding_obj, "deployment") and embedding_obj.deployment:
                return str(embedding_obj.deployment)
            if hasattr(embedding_obj, "model") and embedding_obj.model:
                return str(embedding_obj.model)
            if hasattr(embedding_obj, "model_id") and embedding_obj.model_id:
                return str(embedding_obj.model_id)
            if hasattr(embedding_obj, "model_name") and embedding_obj.model_name:
                return str(embedding_obj.model_name)

        # Try to get from embedding component (legacy single embedding)
        if hasattr(self, "embedding") and self.embedding:
            # Handle list of embeddings
            if isinstance(self.embedding, list) and len(self.embedding) > 0:
                first_emb = self.embedding[0]
                if hasattr(first_emb, "deployment") and first_emb.deployment:
                    return str(first_emb.deployment)
                if hasattr(first_emb, "model") and first_emb.model:
                    return str(first_emb.model)
                if hasattr(first_emb, "model_id") and first_emb.model_id:
                    return str(first_emb.model_id)
                if hasattr(first_emb, "model_name") and first_emb.model_name:
                    return str(first_emb.model_name)
            # Handle single embedding
            elif not isinstance(self.embedding, list):
                if hasattr(self.embedding, "deployment") and self.embedding.deployment:
                    return str(self.embedding.deployment)
                if hasattr(self.embedding, "model") and self.embedding.model:
                    return str(self.embedding.model)
                if hasattr(self.embedding, "model_id") and self.embedding.model_id:
                    return str(self.embedding.model_id)
                if hasattr(self.embedding, "model_name") and self.embedding.model_name:
                    return str(self.embedding.model_name)

        msg = (
            "Could not determine embedding model name. "
            "Please set the 'embedding_model_name' field or ensure the embedding component "
            "has a 'deployment', 'model', 'model_id', or 'model_name' attribute."
        )
        raise ValueError(msg)

    # ---------- helper functions for index management ----------
    def _default_text_mapping(
        self,
        dim: int,
        engine: str = "jvector",
        space_type: str = "l2",
        ef_search: int = 512,
        ef_construction: int = 100,
        m: int = 16,
        vector_field: str = "vector_field",
    ) -> dict[str, Any]:
        """Create the default OpenSearch index mapping for vector search.

        This method generates the index configuration with k-NN settings optimized
        for approximate nearest neighbor search using the specified vector engine.
        Includes the embedding_model keyword field for tracking which model was used.

        Args:
            dim: Dimensionality of the vector embeddings
            engine: Vector search engine (jvector, nmslib, faiss, lucene)
            space_type: Distance metric for similarity calculation
            ef_search: Size of dynamic list used during search
            ef_construction: Size of dynamic list used during index construction
            m: Number of bidirectional links for each vector
            vector_field: Name of the field storing vector embeddings

        Returns:
            Dictionary containing OpenSearch index mapping configuration
        """
        return {
            "settings": {"index": {"knn": True, "knn.algo_param.ef_search": ef_search}},
            "mappings": {
                "properties": {
                    vector_field: {
                        "type": "knn_vector",
                        "dimension": dim,
                        "method": {
                            "name": "disk_ann",
                            "space_type": space_type,
                            "engine": engine,
                            "parameters": {"ef_construction": ef_construction, "m": m},
                        },
                    },
                    "embedding_model": {"type": "keyword"},  # Track which model was used
                    "embedding_dimensions": {"type": "integer"},
                }
            },
        }

    def _ensure_embedding_field_mapping(
        self,
        client: OpenSearch,
        index_name: str,
        field_name: str,
        dim: int,
        engine: str,
        space_type: str,
        ef_construction: int,
        m: int,
    ) -> None:
        """Lazily add a dynamic embedding field to the index if it doesn't exist.

        This allows adding new embedding models without recreating the entire index.
        Also ensures the embedding_model tracking field exists.

        Args:
            client: OpenSearch client instance
            index_name: Target index name
            field_name: Dynamic field name for this embedding model
            dim: Vector dimensionality
            engine: Vector search engine
            space_type: Distance metric
            ef_construction: Construction parameter
            m: HNSW parameter
        """
        try:
            mapping = {
                "properties": {
                    field_name: {
                        "type": "knn_vector",
                        "dimension": dim,
                        "method": {
                            "name": "disk_ann",
                            "space_type": space_type,
                            "engine": engine,
                            "parameters": {"ef_construction": ef_construction, "m": m},
                        },
                    },
                    # Also ensure the embedding_model tracking field exists as keyword
                    "embedding_model": {"type": "keyword"},
                    "embedding_dimensions": {"type": "integer"},
                }
            }
            client.indices.put_mapping(index=index_name, body=mapping)
            logger.info(f"Added/updated embedding field mapping: {field_name}")
        except Exception as e:
            logger.warning(f"Could not add embedding field mapping for {field_name}: {e}")
            raise

        properties = self._get_index_properties(client)
        if not self._is_knn_vector_field(properties, field_name):
            msg = f"Field '{field_name}' is not mapped as knn_vector. Current mapping: {properties.get(field_name)}"
            logger.aerror(msg)
            raise ValueError(msg)

    def _validate_aoss_with_engines(self, *, is_aoss: bool, engine: str) -> None:
        """Validate engine compatibility with Amazon OpenSearch Serverless (AOSS).

        Amazon OpenSearch Serverless has restrictions on which vector engines
        can be used. This method ensures the selected engine is compatible.

        Args:
            is_aoss: Whether the connection is to Amazon OpenSearch Serverless
            engine: The selected vector search engine

        Raises:
            ValueError: If AOSS is used with an incompatible engine
        """
        if is_aoss and engine not in {"nmslib", "faiss"}:
            msg = "Amazon OpenSearch Service Serverless only supports `nmslib` or `faiss` engines"
            raise ValueError(msg)

    def _is_aoss_enabled(self, http_auth: Any) -> bool:
        """Determine if Amazon OpenSearch Serverless (AOSS) is being used.

        Args:
            http_auth: The HTTP authentication object

        Returns:
            True if AOSS is enabled, False otherwise
        """
        return http_auth is not None and hasattr(http_auth, "service") and http_auth.service == "aoss"

    def _bulk_ingest_embeddings(
        self,
        client: OpenSearch,
        index_name: str,
        embeddings: list[list[float]],
        texts: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
        vector_field: str = "vector_field",
        text_field: str = "text",
        embedding_model: str = "unknown",
        mapping: dict | None = None,
        max_chunk_bytes: int | None = 1 * 1024 * 1024,
        *,
        is_aoss: bool = False,
    ) -> list[str]:
        """Efficiently ingest multiple documents with embeddings into OpenSearch.

        This method uses bulk operations to insert documents with their vector
        embeddings and metadata into the specified OpenSearch index. Each document
        is tagged with the embedding_model name for tracking.

        Args:
            client: OpenSearch client instance
            index_name: Target index for document storage
            embeddings: List of vector embeddings for each document
            texts: List of document texts
            metadatas: Optional metadata dictionaries for each document
            ids: Optional document IDs (UUIDs generated if not provided)
            vector_field: Field name for storing vector embeddings
            text_field: Field name for storing document text
            embedding_model: Name of the embedding model used
            mapping: Optional index mapping configuration
            max_chunk_bytes: Maximum size per bulk request chunk
            is_aoss: Whether using Amazon OpenSearch Serverless

        Returns:
            List of document IDs that were successfully ingested
        """
        if not mapping:
            mapping = {}

        requests = []
        return_ids = []
        vector_dimensions = len(embeddings[0]) if embeddings else None

        for i, text in enumerate(texts):
            metadata = metadatas[i] if metadatas else {}
            if vector_dimensions is not None and "embedding_dimensions" not in metadata:
                metadata = {**metadata, "embedding_dimensions": vector_dimensions}
            _id = ids[i] if ids else str(uuid.uuid4())
            request = {
                "_op_type": "index",
                "_index": index_name,
                vector_field: embeddings[i],
                text_field: text,
                "embedding_model": embedding_model,  # Track which model was used
                **metadata,
            }
            if is_aoss:
                request["id"] = _id
            else:
                request["_id"] = _id
            requests.append(request)
            return_ids.append(_id)
        if metadatas:
            self.log(f"Sample metadata: {metadatas[0] if metadatas else {}}")
        helpers.bulk(client, requests, max_chunk_bytes=max_chunk_bytes)
        return return_ids

    # ---------- auth / client ----------
    def _build_auth_kwargs(self) -> dict[str, Any]:
        """Build authentication configuration for OpenSearch client.

        Constructs the appropriate authentication parameters based on the
        selected auth mode (basic username/password or JWT token).

        Returns:
            Dictionary containing authentication configuration

        Raises:
            ValueError: If required authentication parameters are missing
        """
        mode = (self.auth_mode or "basic").strip().lower()
        if mode == "jwt":
            token = (self.jwt_token or "").strip()
            if not token:
                msg = "Auth Mode is 'jwt' but no jwt_token was provided."
                raise ValueError(msg)
            header_name = (self.jwt_header or "Authorization").strip()
            header_value = f"Bearer {token}" if self.bearer_prefix else token
            return {"headers": {header_name: header_value}}
        user = (self.username or "").strip()
        pwd = (self.password or "").strip()
        if not user or not pwd:
            msg = "Auth Mode is 'basic' but username/password are missing."
            raise ValueError(msg)
        return {"http_auth": (user, pwd)}

    def build_client(self) -> OpenSearch:
        """Create and configure an OpenSearch client instance.

        Returns:
            Configured OpenSearch client ready for operations
        """
        auth_kwargs = self._build_auth_kwargs()
        return OpenSearch(
            hosts=[self.opensearch_url],
            use_ssl=self.use_ssl,
            verify_certs=self.verify_certs,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
            **auth_kwargs,
        )

    @check_cached_vector_store
    def build_vector_store(self) -> OpenSearch:
        # Return raw OpenSearch client as our "vector store."
        client = self.build_client()

        # Check if we're in ingestion-only mode (no search query)
        has_search_query = bool((self.search_query or "").strip())
        if not has_search_query:
            logger.debug("Ingestion-only mode activated: search operations will be skipped")
            logger.debug("Starting ingestion mode...")

        logger.warning(f"Embedding: {self.embedding}")
        self._add_documents_to_vector_store(client=client)
        return client

    # ---------- ingest ----------
    def _add_documents_to_vector_store(self, client: OpenSearch) -> None:
        """Process and ingest documents into the OpenSearch vector store.

        This method handles the complete document ingestion pipeline:
        - Prepares document data and metadata
        - Generates vector embeddings using the selected model
        - Creates appropriate index mappings with dynamic field names
        - Bulk inserts documents with vectors and model tracking

        Args:
            client: OpenSearch client for performing operations
        """
        logger.debug("[INGESTION] _add_documents_to_vector_store called")
        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        logger.debug(
            f"[INGESTION] ingest_data type: "
            f"{type(self.ingest_data)}, length: {len(self.ingest_data) if self.ingest_data else 0}"
        )
        logger.debug(
            f"[INGESTION] ingest_data content: "
            f"{self.ingest_data[:2] if self.ingest_data and len(self.ingest_data) > 0 else 'empty'}"
        )

        docs = self.ingest_data or []
        if not docs:
            logger.debug("Ingestion complete: No documents provided")
            return

        if not self.embedding:
            msg = "Embedding handle is required to embed documents."
            raise ValueError(msg)

        # Normalize embedding to list first
        embeddings_list = self.embedding if isinstance(self.embedding, list) else [self.embedding]

        # Filter out None values (fail-safe mode) - do this BEFORE checking if empty
        embeddings_list = [e for e in embeddings_list if e is not None]

        # NOW check if we have any valid embeddings left after filtering
        if not embeddings_list:
            logger.warning("All embeddings returned None (fail-safe mode enabled). Skipping document ingestion.")
            self.log("Embedding returned None (fail-safe mode enabled). Skipping document ingestion.")
            return

        logger.debug(f"[INGESTION] Valid embeddings after filtering: {len(embeddings_list)}")
        self.log(f"Available embedding models: {len(embeddings_list)}")

        # Select the embedding to use for ingestion
        selected_embedding = None
        embedding_model = None

        # If embedding_model_name is specified, find matching embedding
        if hasattr(self, "embedding_model_name") and self.embedding_model_name and self.embedding_model_name.strip():
            target_model_name = self.embedding_model_name.strip()
            self.log(f"Looking for embedding model: {target_model_name}")

            for emb_obj in embeddings_list:
                # Check all possible model identifiers (deployment, model, model_id, model_name)
                # Also check available_models list from EmbeddingsWithModels
                possible_names = []
                deployment = getattr(emb_obj, "deployment", None)
                model = getattr(emb_obj, "model", None)
                model_id = getattr(emb_obj, "model_id", None)
                model_name = getattr(emb_obj, "model_name", None)
                available_models_attr = getattr(emb_obj, "available_models", None)

                if deployment:
                    possible_names.append(str(deployment))
                if model:
                    possible_names.append(str(model))
                if model_id:
                    possible_names.append(str(model_id))
                if model_name:
                    possible_names.append(str(model_name))

                # Also add combined identifier
                if deployment and model and deployment != model:
                    possible_names.append(f"{deployment}:{model}")

                # Add all models from available_models dict
                if available_models_attr and isinstance(available_models_attr, dict):
                    possible_names.extend(
                        str(model_key).strip()
                        for model_key in available_models_attr
                        if model_key and str(model_key).strip()
                    )

                # Match if target matches any of the possible names
                if target_model_name in possible_names:
                    # Check if target is in available_models dict - use dedicated instance
                    if (
                        available_models_attr
                        and isinstance(available_models_attr, dict)
                        and target_model_name in available_models_attr
                    ):
                        # Use the dedicated embedding instance from the dict
                        selected_embedding = available_models_attr[target_model_name]
                        embedding_model = target_model_name
                        self.log(f"Found dedicated embedding instance for '{embedding_model}' in available_models dict")
                    else:
                        # Traditional identifier match
                        selected_embedding = emb_obj
                        embedding_model = self._get_embedding_model_name(emb_obj)
                        self.log(f"Found matching embedding model: {embedding_model} (matched on: {target_model_name})")
                    break

            if not selected_embedding:
                # Build detailed list of available embeddings with all their identifiers
                available_info = []
                for idx, emb in enumerate(embeddings_list):
                    emb_type = type(emb).__name__
                    identifiers = []
                    deployment = getattr(emb, "deployment", None)
                    model = getattr(emb, "model", None)
                    model_id = getattr(emb, "model_id", None)
                    model_name = getattr(emb, "model_name", None)
                    available_models_attr = getattr(emb, "available_models", None)

                    if deployment:
                        identifiers.append(f"deployment='{deployment}'")
                    if model:
                        identifiers.append(f"model='{model}'")
                    if model_id:
                        identifiers.append(f"model_id='{model_id}'")
                    if model_name:
                        identifiers.append(f"model_name='{model_name}'")

                    # Add combined identifier as an option
                    if deployment and model and deployment != model:
                        identifiers.append(f"combined='{deployment}:{model}'")

                    # Add available_models dict if present
                    if available_models_attr and isinstance(available_models_attr, dict):
                        identifiers.append(f"available_models={list(available_models_attr.keys())}")

                    available_info.append(
                        f"  [{idx}] {emb_type}: {', '.join(identifiers) if identifiers else 'No identifiers'}"
                    )

                msg = (
                    f"Embedding model '{target_model_name}' not found in available embeddings.\n\n"
                    f"Available embeddings:\n" + "\n".join(available_info) + "\n\n"
                    "Please set 'embedding_model_name' to one of the identifier values shown above "
                    "(use the value after the '=' sign, without quotes).\n"
                    "For duplicate deployments, use the 'combined' format.\n"
                    "Or leave it empty to use the first embedding."
                )
                raise ValueError(msg)
        else:
            # Use first embedding if no model name specified
            selected_embedding = embeddings_list[0]
            embedding_model = self._get_embedding_model_name(selected_embedding)
            self.log(f"No embedding_model_name specified, using first embedding: {embedding_model}")

        dynamic_field_name = get_embedding_field_name(embedding_model)

        logger.info(f"Selected embedding model for ingestion: '{embedding_model}'")
        self.log(f"Using embedding model for ingestion: {embedding_model}")
        self.log(f"Dynamic vector field: {dynamic_field_name}")

        # Log embedding details for debugging
        if hasattr(selected_embedding, "deployment"):
            logger.info(f"Embedding deployment: {selected_embedding.deployment}")
        if hasattr(selected_embedding, "model"):
            logger.info(f"Embedding model: {selected_embedding.model}")
        if hasattr(selected_embedding, "model_id"):
            logger.info(f"Embedding model_id: {selected_embedding.model_id}")
        if hasattr(selected_embedding, "dimensions"):
            logger.info(f"Embedding dimensions: {selected_embedding.dimensions}")
        if hasattr(selected_embedding, "available_models"):
            logger.info(f"Embedding available_models: {selected_embedding.available_models}")

        # No model switching needed - each model in available_models has its own dedicated instance
        # The selected_embedding is already configured correctly for the target model
        logger.info(f"Using embedding instance for '{embedding_model}' - pre-configured and ready to use")

        # Extract texts and metadata from documents
        texts = []
        metadatas = []
        # Process docs_metadata table input into a dict
        additional_metadata = {}
        logger.debug(f"[LF] Docs metadata {self.docs_metadata}")
        if hasattr(self, "docs_metadata") and self.docs_metadata:
            logger.info(f"[LF] Docs metadata {self.docs_metadata}")
            if isinstance(self.docs_metadata[-1], Data):
                logger.info(f"[LF] Docs metadata is a Data object {self.docs_metadata}")
                self.docs_metadata = self.docs_metadata[-1].data
                logger.info(f"[LF] Docs metadata is a Data object {self.docs_metadata}")
                additional_metadata.update(self.docs_metadata)
            else:
                for item in self.docs_metadata:
                    if isinstance(item, dict) and "key" in item and "value" in item:
                        additional_metadata[item["key"]] = item["value"]
        # Replace string "None" values with actual None
        for key, value in additional_metadata.items():
            if value == "None":
                additional_metadata[key] = None
        logger.info(f"[LF] Additional metadata {additional_metadata}")
        for doc_obj in docs:
            data_copy = json.loads(doc_obj.model_dump_json())
            text = data_copy.pop(doc_obj.text_key, doc_obj.default_value)
            texts.append(text)

            # Merge additional metadata from table input
            data_copy.update(additional_metadata)

            metadatas.append(data_copy)
        self.log(metadatas)

        # Generate embeddings with rate-limit-aware retry logic using tenacity
        from tenacity import (
            retry,
            retry_if_exception,
            stop_after_attempt,
            wait_exponential,
        )

        def is_rate_limit_error(exception: Exception) -> bool:
            """Check if exception is a rate limit error (429)."""
            error_str = str(exception).lower()
            return "429" in error_str or "rate_limit" in error_str or "rate limit" in error_str

        def is_other_retryable_error(exception: Exception) -> bool:
            """Check if exception is retryable but not a rate limit error."""
            # Retry on most exceptions except for specific non-retryable ones
            # Add other non-retryable exceptions here if needed
            return not is_rate_limit_error(exception)

        # Create retry decorator for rate limit errors (longer backoff)
        retry_on_rate_limit = retry(
            retry=retry_if_exception(is_rate_limit_error),
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=2, min=2, max=30),
            reraise=True,
            before_sleep=lambda retry_state: logger.warning(
                f"Rate limit hit for chunk (attempt {retry_state.attempt_number}/5), "
                f"backing off for {retry_state.next_action.sleep:.1f}s"
            ),
        )

        # Create retry decorator for other errors (shorter backoff)
        retry_on_other_errors = retry(
            retry=retry_if_exception(is_other_retryable_error),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
            before_sleep=lambda retry_state: logger.warning(
                f"Error embedding chunk (attempt {retry_state.attempt_number}/3), "
                f"retrying in {retry_state.next_action.sleep:.1f}s: {retry_state.outcome.exception()}"
            ),
        )

        def embed_chunk_with_retry(chunk_text: str, chunk_idx: int) -> list[float]:
            """Embed a single chunk with rate-limit-aware retry logic."""

            @retry_on_rate_limit
            @retry_on_other_errors
            def _embed(text: str) -> list[float]:
                return selected_embedding.embed_documents([text])[0]

            try:
                return _embed(chunk_text)
            except Exception as e:
                logger.error(
                    f"Failed to embed chunk {chunk_idx} after all retries: {e}",
                    error=str(e),
                )
                raise

        # Restrict concurrency for IBM/Watsonx models to avoid rate limits
        is_ibm = (embedding_model and "ibm" in str(embedding_model).lower()) or (
            selected_embedding and "watsonx" in type(selected_embedding).__name__.lower()
        )
        logger.debug(f"Is IBM: {is_ibm}")

        # For IBM models, use sequential processing with rate limiting
        # For other models, use parallel processing
        vectors: list[list[float]] = [None] * len(texts)

        if is_ibm:
            # Sequential processing with inter-request delay for IBM models
            inter_request_delay = 0.6  # ~1.67 req/s, safely under 2 req/s limit
            logger.info(f"Using sequential processing for IBM model with {inter_request_delay}s delay between requests")

            for idx, chunk in enumerate(texts):
                if idx > 0:
                    # Add delay between requests (but not before the first one)
                    time.sleep(inter_request_delay)
                vectors[idx] = embed_chunk_with_retry(chunk, idx)
        else:
            # Parallel processing for non-IBM models
            max_workers = min(max(len(texts), 1), 8)
            logger.debug(f"Using parallel processing with {max_workers} workers")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(embed_chunk_with_retry, chunk, idx): idx for idx, chunk in enumerate(texts)}
                for future in as_completed(futures):
                    idx = futures[future]
                    vectors[idx] = future.result()

        if not vectors:
            self.log(f"No vectors generated from documents for model {embedding_model}.")
            return

        # Get vector dimension for mapping
        dim = len(vectors[0]) if vectors else 768  # default fallback

        # Check for AOSS
        auth_kwargs = self._build_auth_kwargs()
        is_aoss = self._is_aoss_enabled(auth_kwargs.get("http_auth"))

        # Validate engine with AOSS
        engine = getattr(self, "engine", "jvector")
        self._validate_aoss_with_engines(is_aoss=is_aoss, engine=engine)

        # Create mapping with proper KNN settings
        space_type = getattr(self, "space_type", "l2")
        ef_construction = getattr(self, "ef_construction", 512)
        m = getattr(self, "m", 16)

        mapping = self._default_text_mapping(
            dim=dim,
            engine=engine,
            space_type=space_type,
            ef_construction=ef_construction,
            m=m,
            vector_field=dynamic_field_name,  # Use dynamic field name
        )

        # Ensure index exists with baseline mapping
        try:
            if not client.indices.exists(index=self.index_name):
                self.log(f"Creating index '{self.index_name}' with base mapping")
                client.indices.create(index=self.index_name, body=mapping)
        except RequestError as creation_error:
            if creation_error.error != "resource_already_exists_exception":
                logger.warning(f"Failed to create index '{self.index_name}': {creation_error}")

        # Ensure the dynamic field exists in the index
        self._ensure_embedding_field_mapping(
            client=client,
            index_name=self.index_name,
            field_name=dynamic_field_name,
            dim=dim,
            engine=engine,
            space_type=space_type,
            ef_construction=ef_construction,
            m=m,
        )

        self.log(f"Indexing {len(texts)} documents into '{self.index_name}' with model '{embedding_model}'...")
        logger.info(f"Will store embeddings in field: {dynamic_field_name}")
        logger.info(f"Will tag documents with embedding_model: {embedding_model}")

        # Use the bulk ingestion with model tracking
        return_ids = self._bulk_ingest_embeddings(
            client=client,
            index_name=self.index_name,
            embeddings=vectors,
            texts=texts,
            metadatas=metadatas,
            vector_field=dynamic_field_name,  # Use dynamic field name
            text_field="text",
            embedding_model=embedding_model,  # Track the model
            mapping=mapping,
            is_aoss=is_aoss,
        )
        self.log(metadatas)

        logger.info(
            f"Ingestion complete: Successfully indexed {len(return_ids)} documents with model '{embedding_model}'"
        )
        self.log(f"Successfully indexed {len(return_ids)} documents with model {embedding_model}.")

    # ---------- helpers for filters ----------
    def _is_placeholder_term(self, term_obj: dict) -> bool:
        # term_obj like {"filename": "__IMPOSSIBLE_VALUE__"}
        return any(v == "__IMPOSSIBLE_VALUE__" for v in term_obj.values())

    def _coerce_filter_clauses(self, filter_obj: dict | None) -> list[dict]:
        """Convert filter expressions into OpenSearch-compatible filter clauses.

        This method accepts two filter formats and converts them to standardized
        OpenSearch query clauses:

        Format A - Explicit filters:
        {"filter": [{"term": {"field": "value"}}, {"terms": {"field": ["val1", "val2"]}}],
         "limit": 10, "score_threshold": 1.5}

        Format B - Context-style mapping:
        {"data_sources": ["file1.pdf"], "document_types": ["pdf"], "owners": ["user1"]}

        Args:
            filter_obj: Filter configuration dictionary or None

        Returns:
            List of OpenSearch filter clauses (term/terms objects)
            Placeholder values with "__IMPOSSIBLE_VALUE__" are ignored
        """
        if not filter_obj:
            return []

        # If it is a string, try to parse it once
        if isinstance(filter_obj, str):
            try:
                filter_obj = json.loads(filter_obj)
            except json.JSONDecodeError:
                # Not valid JSON - treat as no filters
                return []

        # Case A: already an explicit list/dict under "filter"
        if "filter" in filter_obj:
            raw = filter_obj["filter"]
            if isinstance(raw, dict):
                raw = [raw]
            explicit_clauses: list[dict] = []
            for f in raw or []:
                if "term" in f and isinstance(f["term"], dict) and not self._is_placeholder_term(f["term"]):
                    explicit_clauses.append(f)
                elif "terms" in f and isinstance(f["terms"], dict):
                    field, vals = next(iter(f["terms"].items()))
                    if isinstance(vals, list) and len(vals) > 0:
                        explicit_clauses.append(f)
            return explicit_clauses

        # Case B: convert context-style maps into clauses
        field_mapping = {
            "data_sources": "filename",
            "document_types": "mimetype",
            "owners": "owner",
        }
        context_clauses: list[dict] = []
        for k, values in filter_obj.items():
            if not isinstance(values, list):
                continue
            field = field_mapping.get(k, k)
            if len(values) == 0:
                # Match-nothing placeholder (kept to mirror your tool semantics)
                context_clauses.append({"term": {field: "__IMPOSSIBLE_VALUE__"}})
            elif len(values) == 1:
                if values[0] != "__IMPOSSIBLE_VALUE__":
                    context_clauses.append({"term": {field: values[0]}})
            else:
                context_clauses.append({"terms": {field: values}})
        return context_clauses

    def _detect_available_models(self, client: OpenSearch, filter_clauses: list[dict] | None = None) -> list[str]:
        """Detect which embedding models have documents in the index.

        Uses aggregation to find all unique embedding_model values, optionally
        filtered to only documents matching the user's filter criteria.

        Args:
            client: OpenSearch client instance
            filter_clauses: Optional filter clauses to scope model detection

        Returns:
            List of embedding model names found in the index
        """
        try:
            agg_query = {"size": 0, "aggs": {"embedding_models": {"terms": {"field": "embedding_model", "size": 10}}}}

            # Apply filters to model detection if any exist
            if filter_clauses:
                agg_query["query"] = {"bool": {"filter": filter_clauses}}

            logger.debug(f"Model detection query: {agg_query}")
            result = client.search(
                index=self.index_name,
                body=agg_query,
                params={"terminate_after": 0},
            )
            buckets = result.get("aggregations", {}).get("embedding_models", {}).get("buckets", [])
            models = [b["key"] for b in buckets if b["key"]]

            # Log detailed bucket info for debugging
            logger.info(
                f"Detected embedding models in corpus: {models}"
                + (f" (with {len(filter_clauses)} filters)" if filter_clauses else "")
            )
            if not models:
                total_hits = result.get("hits", {}).get("total", {})
                total_count = total_hits.get("value", 0) if isinstance(total_hits, dict) else total_hits
                logger.warning(
                    f"No embedding_model values found in index '{self.index_name}'. "
                    f"Total docs in index: {total_count}. "
                    f"This may indicate documents were indexed without the embedding_model field."
                )
        except (OpenSearchException, KeyError, ValueError) as e:
            logger.warning(f"Failed to detect embedding models: {e}")
            # Fallback to current model
            fallback_model = self._get_embedding_model_name()
            logger.info(f"Using fallback model: {fallback_model}")
            return [fallback_model]
        else:
            return models

    def _get_index_properties(self, client: OpenSearch) -> dict[str, Any] | None:
        """Retrieve flattened mapping properties for the current index."""
        try:
            mapping = client.indices.get_mapping(index=self.index_name)
        except OpenSearchException as e:
            logger.warning(
                f"Failed to fetch mapping for index '{self.index_name}': {e}. Proceeding without mapping metadata."
            )
            return None

        properties: dict[str, Any] = {}
        for index_data in mapping.values():
            props = index_data.get("mappings", {}).get("properties", {})
            if isinstance(props, dict):
                properties.update(props)
        return properties

    def _is_knn_vector_field(self, properties: dict[str, Any] | None, field_name: str) -> bool:
        """Check whether the field is mapped as a knn_vector."""
        if not field_name:
            return False
        if properties is None:
            logger.warning(f"Mapping metadata unavailable; assuming field '{field_name}' is usable.")
            return True
        field_def = properties.get(field_name)
        if not isinstance(field_def, dict):
            return False
        if field_def.get("type") == "knn_vector":
            return True

        nested_props = field_def.get("properties")
        return bool(isinstance(nested_props, dict) and nested_props.get("type") == "knn_vector")

    def _get_field_dimension(self, properties: dict[str, Any] | None, field_name: str) -> int | None:
        """Get the dimension of a knn_vector field from the index mapping.

        Args:
            properties: Index properties from mapping
            field_name: Name of the vector field

        Returns:
            Dimension of the field, or None if not found
        """
        if not field_name or properties is None:
            return None

        field_def = properties.get(field_name)
        if not isinstance(field_def, dict):
            return None

        # Check direct knn_vector field
        if field_def.get("type") == "knn_vector":
            return field_def.get("dimension")

        # Check nested properties
        nested_props = field_def.get("properties")
        if isinstance(nested_props, dict) and nested_props.get("type") == "knn_vector":
            return nested_props.get("dimension")

        return None

    # ---------- search (multi-model hybrid) ----------
    def search(self, query: str | None = None) -> list[dict[str, Any]]:
        """Perform multi-model hybrid search combining multiple vector similarities and keyword matching.

        This method executes a sophisticated search that:
        1. Auto-detects all embedding models present in the index
        2. Generates query embeddings for ALL detected models in parallel
        3. Combines multiple KNN queries using dis_max (picks best match)
        4. Adds keyword search with fuzzy matching (30% weight)
        5. Applies optional filtering and score thresholds
        6. Returns aggregations for faceted search

        Search weights:
        - Semantic search (dis_max across all models): 70%
        - Keyword search: 30%

        Args:
            query: Search query string (used for both vector embedding and keyword search)

        Returns:
            List of search results with page_content, metadata, and relevance scores

        Raises:
            ValueError: If embedding component is not provided or filter JSON is invalid
        """
        logger.info(self.ingest_data)
        client = self.build_client()
        q = (query or "").strip()

        # Parse optional filter expression
        filter_obj = None
        if getattr(self, "filter_expression", "") and self.filter_expression.strip():
            try:
                filter_obj = json.loads(self.filter_expression)
            except json.JSONDecodeError as e:
                msg = f"Invalid filter_expression JSON: {e}"
                raise ValueError(msg) from e

        if not self.embedding:
            msg = "Embedding is required to run hybrid search (KNN + keyword)."
            raise ValueError(msg)

        # Check if embedding is None (fail-safe mode)
        if self.embedding is None or (isinstance(self.embedding, list) and all(e is None for e in self.embedding)):
            logger.error("Embedding returned None (fail-safe mode enabled). Cannot perform search.")
            return []

        # Build filter clauses first so we can use them in model detection
        filter_clauses = self._coerce_filter_clauses(filter_obj)

        # Detect available embedding models in the index (scoped by filters)
        available_models = self._detect_available_models(client, filter_clauses)

        if not available_models:
            logger.warning("No embedding models found in index, using current model")
            available_models = [self._get_embedding_model_name()]

        # Generate embeddings for ALL detected models
        query_embeddings = {}

        # Normalize embedding to list
        embeddings_list = self.embedding if isinstance(self.embedding, list) else [self.embedding]
        # Filter out None values (fail-safe mode)
        embeddings_list = [e for e in embeddings_list if e is not None]

        if not embeddings_list:
            logger.error(
                "No valid embeddings available after filtering None values (fail-safe mode). Cannot perform search."
            )
            return []

        # Create a comprehensive map of model names to embedding objects
        # Check all possible identifiers (deployment, model, model_id, model_name)
        # Also leverage available_models list from EmbeddingsWithModels
        # Handle duplicate identifiers by creating combined keys
        embedding_by_model = {}
        identifier_conflicts = {}  # Track which identifiers have conflicts

        for idx, emb_obj in enumerate(embeddings_list):
            # Get all possible identifiers for this embedding
            identifiers = []
            deployment = getattr(emb_obj, "deployment", None)
            model = getattr(emb_obj, "model", None)
            model_id = getattr(emb_obj, "model_id", None)
            model_name = getattr(emb_obj, "model_name", None)
            dimensions = getattr(emb_obj, "dimensions", None)
            available_models_attr = getattr(emb_obj, "available_models", None)

            logger.info(
                f"Embedding object {idx}: deployment={deployment}, model={model}, "
                f"model_id={model_id}, model_name={model_name}, dimensions={dimensions}, "
                f"available_models={available_models_attr}"
            )

            # If this embedding has available_models dict, map all models to their dedicated instances
            if available_models_attr and isinstance(available_models_attr, dict):
                logger.info(
                    f"Embedding object {idx} provides {len(available_models_attr)} models via available_models dict"
                )
                for model_name_key, dedicated_embedding in available_models_attr.items():
                    if model_name_key and str(model_name_key).strip():
                        model_str = str(model_name_key).strip()
                        if model_str not in embedding_by_model:
                            # Use the dedicated embedding instance from the dict
                            embedding_by_model[model_str] = dedicated_embedding
                            logger.info(f"Mapped available model '{model_str}' to dedicated embedding instance")
                        else:
                            # Conflict detected - track it
                            if model_str not in identifier_conflicts:
                                identifier_conflicts[model_str] = [embedding_by_model[model_str]]
                            identifier_conflicts[model_str].append(dedicated_embedding)
                            logger.warning(f"Available model '{model_str}' has conflict - used by multiple embeddings")

            # Also map traditional identifiers (for backward compatibility)
            if deployment:
                identifiers.append(str(deployment))
            if model:
                identifiers.append(str(model))
            if model_id:
                identifiers.append(str(model_id))
            if model_name:
                identifiers.append(str(model_name))

            # Map all identifiers to this embedding object
            for identifier in identifiers:
                if identifier not in embedding_by_model:
                    embedding_by_model[identifier] = emb_obj
                    logger.info(f"Mapped identifier '{identifier}' to embedding object {idx}")
                else:
                    # Conflict detected - track it
                    if identifier not in identifier_conflicts:
                        identifier_conflicts[identifier] = [embedding_by_model[identifier]]
                    identifier_conflicts[identifier].append(emb_obj)
                    logger.warning(f"Identifier '{identifier}' has conflict - used by multiple embeddings")

            # For embeddings with model+deployment, create combined identifier
            # This helps when deployment is the same but model differs
            if deployment and model and deployment != model:
                combined_id = f"{deployment}:{model}"
                if combined_id not in embedding_by_model:
                    embedding_by_model[combined_id] = emb_obj
                    logger.info(f"Created combined identifier '{combined_id}' for embedding object {idx}")

        # Log conflicts
        if identifier_conflicts:
            logger.warning(
                f"Found {len(identifier_conflicts)} conflicting identifiers. "
                f"Consider using combined format 'deployment:model' or specifying unique model names."
            )
            for conflict_id, emb_list in identifier_conflicts.items():
                logger.warning(f"  Conflict on '{conflict_id}': {len(emb_list)} embeddings use this identifier")

        logger.info(f"Generating embeddings for {len(available_models)} models in index")
        logger.info(f"Available embedding identifiers: {list(embedding_by_model.keys())}")
        self.log(f"[SEARCH] Models detected in index: {available_models}")
        self.log(f"[SEARCH] Available embedding identifiers: {list(embedding_by_model.keys())}")

        # Track matching status for debugging
        matched_models = []
        unmatched_models = []

        for model_name in available_models:
            try:
                # Check if we have an embedding object for this model
                if model_name in embedding_by_model:
                    # Use the matching embedding object directly
                    emb_obj = embedding_by_model[model_name]
                    emb_deployment = getattr(emb_obj, "deployment", None)
                    emb_model = getattr(emb_obj, "model", None)
                    emb_model_id = getattr(emb_obj, "model_id", None)
                    emb_dimensions = getattr(emb_obj, "dimensions", None)
                    emb_available_models = getattr(emb_obj, "available_models", None)

                    logger.info(
                        f"Using embedding object for model '{model_name}': "
                        f"deployment={emb_deployment}, model={emb_model}, model_id={emb_model_id}, "
                        f"dimensions={emb_dimensions}"
                    )

                    # Check if this is a dedicated instance from available_models dict
                    if emb_available_models and isinstance(emb_available_models, dict):
                        logger.info(
                            f"Model '{model_name}' using dedicated instance from available_models dict "
                            f"(pre-configured with correct model and dimensions)"
                        )

                    # Use the embedding instance directly - no model switching needed!
                    vec = emb_obj.embed_query(q)
                    query_embeddings[model_name] = vec
                    matched_models.append(model_name)
                    logger.info(f"Generated embedding for model: {model_name} (actual dimensions: {len(vec)})")
                    self.log(f"[MATCH] Model '{model_name}' - generated {len(vec)}-dim embedding")
                else:
                    # No matching embedding found for this model
                    unmatched_models.append(model_name)
                    logger.warning(
                        f"No matching embedding found for model '{model_name}'. "
                        f"This model will be skipped. Available identifiers: {list(embedding_by_model.keys())}"
                    )
                    self.log(f"[NO MATCH] Model '{model_name}' - available: {list(embedding_by_model.keys())}")
            except (RuntimeError, ValueError, ConnectionError, TimeoutError, AttributeError, KeyError) as e:
                logger.warning(f"Failed to generate embedding for {model_name}: {e}")
                self.log(f"[ERROR] Embedding generation failed for '{model_name}': {e}")

        # Log summary of model matching
        logger.info(f"Model matching summary: {len(matched_models)} matched, {len(unmatched_models)} unmatched")
        self.log(f"[SUMMARY] Model matching: {len(matched_models)} matched, {len(unmatched_models)} unmatched")
        if unmatched_models:
            self.log(f"[WARN] Unmatched models in index: {unmatched_models}")

        if not query_embeddings:
            msg = (
                f"Failed to generate embeddings for any model. "
                f"Index has models: {available_models}, but no matching embedding objects found. "
                f"Available embedding identifiers: {list(embedding_by_model.keys())}"
            )
            self.log(f"[FAIL] Search failed: {msg}")
            raise ValueError(msg)

        index_properties = self._get_index_properties(client)
        legacy_vector_field = getattr(self, "vector_field", "chunk_embedding")

        # Build KNN queries for each model
        embedding_fields: list[str] = []
        knn_queries_with_candidates = []
        knn_queries_without_candidates = []

        raw_num_candidates = getattr(self, "num_candidates", 1000)
        try:
            num_candidates = int(raw_num_candidates) if raw_num_candidates is not None else 0
        except (TypeError, ValueError):
            num_candidates = 0
        use_num_candidates = num_candidates > 0

        for model_name, embedding_vector in query_embeddings.items():
            field_name = get_embedding_field_name(model_name)
            selected_field = field_name
            vector_dim = len(embedding_vector)

            # Only use the expected dynamic field - no legacy fallback
            # This prevents dimension mismatches between models
            if not self._is_knn_vector_field(index_properties, selected_field):
                logger.warning(
                    f"Skipping model {model_name}: field '{field_name}' is not mapped as knn_vector. "
                    f"Documents must be indexed with this embedding model before querying."
                )
                self.log(f"[SKIP] Field '{selected_field}' not a knn_vector - skipping model '{model_name}'")
                continue

            # Validate vector dimensions match the field dimensions
            field_dim = self._get_field_dimension(index_properties, selected_field)
            if field_dim is not None and field_dim != vector_dim:
                logger.error(
                    f"Dimension mismatch for model '{model_name}': "
                    f"Query vector has {vector_dim} dimensions but field '{selected_field}' expects {field_dim}. "
                    f"Skipping this model to prevent search errors."
                )
                self.log(f"[DIM MISMATCH] Model '{model_name}': query={vector_dim} vs field={field_dim} - skipping")
                continue

            logger.info(
                f"Adding KNN query for model '{model_name}': field='{selected_field}', "
                f"query_dims={vector_dim}, field_dims={field_dim or 'unknown'}"
            )
            embedding_fields.append(selected_field)

            base_query = {
                "knn": {
                    selected_field: {
                        "vector": embedding_vector,
                        "k": 50,
                    }
                }
            }

            if use_num_candidates:
                query_with_candidates = copy.deepcopy(base_query)
                query_with_candidates["knn"][selected_field]["num_candidates"] = num_candidates
            else:
                query_with_candidates = base_query

            knn_queries_with_candidates.append(query_with_candidates)
            knn_queries_without_candidates.append(base_query)

        if not knn_queries_with_candidates:
            # No valid fields found - this can happen when:
            # 1. Index is empty (no documents yet)
            # 2. Embedding model has changed and field doesn't exist yet
            # Return empty results instead of failing
            logger.warning(
                "No valid knn_vector fields found for embedding models. "
                "This may indicate an empty index or missing field mappings. "
                "Returning empty search results."
            )
            self.log(
                f"[WARN] No valid KNN queries could be built. "
                f"Query embeddings generated: {list(query_embeddings.keys())}, "
                f"but no matching knn_vector fields found in index."
            )
            return []

        # Build exists filter - document must have at least one embedding field
        exists_any_embedding = {
            "bool": {"should": [{"exists": {"field": f}} for f in set(embedding_fields)], "minimum_should_match": 1}
        }

        # Combine user filters with exists filter
        all_filters = [*filter_clauses, exists_any_embedding]

        # Get limit and score threshold
        limit = (filter_obj or {}).get("limit", self.number_of_results)
        score_threshold = (filter_obj or {}).get("score_threshold", 0)

        # Build multi-model hybrid query
        body = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "dis_max": {
                                "tie_breaker": 0.0,  # Take only the best match, no blending
                                "boost": 0.7,  # 70% weight for semantic search
                                "queries": knn_queries_with_candidates,
                            }
                        },
                        {
                            "multi_match": {
                                "query": q,
                                "fields": ["text^2", "filename^1.5"],
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                                "boost": 0.3,  # 30% weight for keyword search
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                    "filter": all_filters,
                }
            },
            "aggs": {
                "data_sources": {"terms": {"field": "filename", "size": 20}},
                "document_types": {"terms": {"field": "mimetype", "size": 10}},
                "owners": {"terms": {"field": "owner", "size": 10}},
                "embedding_models": {"terms": {"field": "embedding_model", "size": 10}},
            },
            "_source": [
                "filename",
                "mimetype",
                "page",
                "text",
                "source_url",
                "owner",
                "embedding_model",
                "allowed_users",
                "allowed_groups",
            ],
            "size": limit,
        }

        if isinstance(score_threshold, (int, float)) and score_threshold > 0:
            body["min_score"] = score_threshold

        logger.info(
            f"Executing multi-model hybrid search with {len(knn_queries_with_candidates)} embedding models: "
            f"{list(query_embeddings.keys())}"
        )
        self.log(f"[EXEC] Executing search with {len(knn_queries_with_candidates)} KNN queries, limit={limit}")
        self.log(f"[EXEC] Embedding models used: {list(query_embeddings.keys())}")
        self.log(f"[EXEC] KNN fields being queried: {embedding_fields}")

        try:
            resp = client.search(index=self.index_name, body=body, params={"terminate_after": 0})
        except RequestError as e:
            error_message = str(e)
            lowered = error_message.lower()
            if use_num_candidates and "num_candidates" in lowered:
                logger.warning(
                    "Retrying search without num_candidates parameter due to cluster capabilities",
                    error=error_message,
                )
                fallback_body = copy.deepcopy(body)
                try:
                    fallback_body["query"]["bool"]["should"][0]["dis_max"]["queries"] = knn_queries_without_candidates
                except (KeyError, IndexError, TypeError) as inner_err:
                    raise e from inner_err
                resp = client.search(
                    index=self.index_name,
                    body=fallback_body,
                    params={"terminate_after": 0},
                )
            elif "knn_vector" in lowered or ("field" in lowered and "knn" in lowered):
                fallback_vector = next(iter(query_embeddings.values()), None)
                if fallback_vector is None:
                    raise
                fallback_field = legacy_vector_field or "chunk_embedding"
                logger.warning(
                    "KNN search failed for dynamic fields; falling back to legacy field '%s'.",
                    fallback_field,
                )
                fallback_body = copy.deepcopy(body)
                fallback_body["query"]["bool"]["filter"] = filter_clauses
                knn_fallback = {
                    "knn": {
                        fallback_field: {
                            "vector": fallback_vector,
                            "k": 50,
                        }
                    }
                }
                if use_num_candidates:
                    knn_fallback["knn"][fallback_field]["num_candidates"] = num_candidates
                fallback_body["query"]["bool"]["should"][0]["dis_max"]["queries"] = [knn_fallback]
                resp = client.search(
                    index=self.index_name,
                    body=fallback_body,
                    params={"terminate_after": 0},
                )
            else:
                raise
        hits = resp.get("hits", {}).get("hits", [])

        logger.info(f"Found {len(hits)} results")
        self.log(f"[RESULT] Search complete: {len(hits)} results found")

        if len(hits) == 0:
            self.log(
                f"[EMPTY] Debug info: "
                f"models_in_index={available_models}, "
                f"matched_models={matched_models}, "
                f"knn_fields={embedding_fields}, "
                f"filters={len(filter_clauses)} clauses"
            )

        return [
            {
                "page_content": hit["_source"].get("text", ""),
                "metadata": {k: v for k, v in hit["_source"].items() if k != "text"},
                "score": hit.get("_score"),
            }
            for hit in hits
        ]

    def search_documents(self) -> list[Data]:
        """Search documents and return results as Data objects.

        This is the main interface method that performs the multi-model search using the
        configured search_query and returns results in Langflow's Data format.

        Always builds the vector store (triggering ingestion if needed), then performs
        search only if a query is provided.

        Returns:
            List of Data objects containing search results with text and metadata

        Raises:
            Exception: If search operation fails
        """
        try:
            # Always build/cache the vector store to ensure ingestion happens
            logger.info(f"Search query: {self.search_query}")
            if self._cached_vector_store is None:
                self.build_vector_store()

            # Only perform search if query is provided
            search_query = (self.search_query or "").strip()
            if not search_query:
                self.log("No search query provided - ingestion completed, returning empty results")
                return []

            # Perform search with the provided query
            raw = self.search(search_query)
            return [Data(text=hit["page_content"], **hit["metadata"]) for hit in raw]
        except Exception as e:
            self.log(f"search_documents error: {e}")
            raise

    # -------- dynamic UI handling (auth switch) --------
    async def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Dynamically update component configuration based on field changes.

        This method handles real-time UI updates, particularly for authentication
        mode changes that show/hide relevant input fields.

        Args:
            build_config: Current component configuration
            field_value: New value for the changed field
            field_name: Name of the field that changed

        Returns:
            Updated build configuration with appropriate field visibility
        """
        try:
            if field_name == "auth_mode":
                mode = (field_value or "basic").strip().lower()
                is_basic = mode == "basic"
                is_jwt = mode == "jwt"

                build_config["username"]["show"] = is_basic
                build_config["password"]["show"] = is_basic

                build_config["jwt_token"]["show"] = is_jwt
                build_config["jwt_header"]["show"] = is_jwt
                build_config["bearer_prefix"]["show"] = is_jwt

                build_config["username"]["required"] = is_basic
                build_config["password"]["required"] = is_basic

                build_config["jwt_token"]["required"] = is_jwt
                build_config["jwt_header"]["required"] = is_jwt
                build_config["bearer_prefix"]["required"] = False

                return build_config

        except (KeyError, ValueError) as e:
            self.log(f"update_build_config error: {e}")

        return build_config
