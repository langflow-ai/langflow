from __future__ import annotations

import json
import uuid
from typing import Any

from opensearchpy import OpenSearch, helpers

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MultilineInput, SecretStrInput, StrInput, TableInput
from lfx.log import logger
from lfx.schema.data import Data


@vector_store_connection
class OpenSearchVectorStoreComponent(LCVectorStoreComponent):
    """OpenSearch Vector Store Component with Hybrid Search Capabilities.

    This component provides vector storage and retrieval using OpenSearch, combining semantic
    similarity search (KNN) with keyword-based search for optimal results. It supports document
    ingestion, vector embeddings, and advanced filtering with authentication options.

    Features:
    - Vector storage with configurable engines (jvector, nmslib, faiss, lucene)
    - Hybrid search combining KNN vector similarity and keyword matching
    - Flexible authentication (Basic auth, JWT tokens)
    - Advanced filtering and aggregations
    - Metadata injection during document ingestion
    """

    display_name: str = "OpenSearch"
    icon: str = "OpenSearch"
    description: str = (
        "Store and search documents using OpenSearch with hybrid semantic and keyword search capabilities."
    )

    # Keys we consider baseline
    default_keys: list[str] = [
        "opensearch_url",
        "index_name",
        *[i.name for i in LCVectorStoreComponent.inputs],  # search_query, add_documents, etc.
        "embedding",
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
        *LCVectorStoreComponent.inputs,  # includes search_query, add_documents, etc.
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        StrInput(
            name="vector_field",
            display_name="Vector Field Name",
            value="chunk_embedding",
            advanced=True,
            info="Name of the field in OpenSearch documents that stores the vector embeddings for similarity search.",
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
            show=False,
        ),
        SecretStrInput(
            name="password",
            display_name="OpenSearch Password",
            value="admin",
            show=False,
        ),
        SecretStrInput(
            name="jwt_token",
            display_name="JWT Token",
            value="JWT",
            load_from_db=False,
            show=True,
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
                    }
                }
            },
        }

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
        mapping: dict | None = None,
        max_chunk_bytes: int | None = 1 * 1024 * 1024,
        *,
        is_aoss: bool = False,
    ) -> list[str]:
        """Efficiently ingest multiple documents with embeddings into OpenSearch.

        This method uses bulk operations to insert documents with their vector
        embeddings and metadata into the specified OpenSearch index.

        Args:
            client: OpenSearch client instance
            index_name: Target index for document storage
            embeddings: List of vector embeddings for each document
            texts: List of document texts
            metadatas: Optional metadata dictionaries for each document
            ids: Optional document IDs (UUIDs generated if not provided)
            vector_field: Field name for storing vector embeddings
            text_field: Field name for storing document text
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

        for i, text in enumerate(texts):
            metadata = metadatas[i] if metadatas else {}
            _id = ids[i] if ids else str(uuid.uuid4())
            request = {
                "_op_type": "index",
                "_index": index_name,
                vector_field: embeddings[i],
                text_field: text,
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
        # Return raw OpenSearch client as our “vector store.”
        self.log(self.ingest_data)
        client = self.build_client()
        self._add_documents_to_vector_store(client=client)
        return client

    # ---------- ingest ----------
    def _add_documents_to_vector_store(self, client: OpenSearch) -> None:
        """Process and ingest documents into the OpenSearch vector store.

        This method handles the complete document ingestion pipeline:
        - Prepares document data and metadata
        - Generates vector embeddings
        - Creates appropriate index mappings
        - Bulk inserts documents with vectors

        Args:
            client: OpenSearch client for performing operations
        """
        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        docs = self.ingest_data or []
        if not docs:
            self.log("No documents to ingest.")
            return

        # Extract texts and metadata from documents
        texts = []
        metadatas = []
        # Process docs_metadata table input into a dict
        additional_metadata = {}
        if hasattr(self, "docs_metadata") and self.docs_metadata:
            logger.debug(f"[LF] Docs metadata {self.docs_metadata}")
            if isinstance(self.docs_metadata[-1], Data):
                logger.debug(f"[LF] Docs metadata is a Data object {self.docs_metadata}")
                self.docs_metadata = self.docs_metadata[-1].data
                logger.debug(f"[LF] Docs metadata is a Data object {self.docs_metadata}")
                additional_metadata.update(self.docs_metadata)
            else:
                for item in self.docs_metadata:
                    if isinstance(item, dict) and "key" in item and "value" in item:
                        additional_metadata[item["key"]] = item["value"]
        # Replace string "None" values with actual None
        for key, value in additional_metadata.items():
            if value == "None":
                additional_metadata[key] = None
        logger.debug(f"[LF] Additional metadata {additional_metadata}")
        for doc_obj in docs:
            data_copy = json.loads(doc_obj.model_dump_json())
            text = data_copy.pop(doc_obj.text_key, doc_obj.default_value)
            texts.append(text)

            # Merge additional metadata from table input
            data_copy.update(additional_metadata)

            metadatas.append(data_copy)
        self.log(metadatas)
        if not self.embedding:
            msg = "Embedding handle is required to embed documents."
            raise ValueError(msg)

        # Generate embeddings
        vectors = self.embedding.embed_documents(texts)

        if not vectors:
            self.log("No vectors generated from documents.")
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
            vector_field=self.vector_field,
        )

        self.log(f"Indexing {len(texts)} documents into '{self.index_name}' with proper KNN mapping...")

        # Use the LangChain-style bulk ingestion
        return_ids = self._bulk_ingest_embeddings(
            client=client,
            index_name=self.index_name,
            embeddings=vectors,
            texts=texts,
            metadatas=metadatas,
            vector_field=self.vector_field,
            text_field="text",
            mapping=mapping,
            is_aoss=is_aoss,
        )
        self.log(metadatas)

        self.log(f"Successfully indexed {len(return_ids)} documents.")

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

    # ---------- search (single hybrid path matching your tool) ----------
    def search(self, query: str | None = None) -> list[dict[str, Any]]:
        """Perform hybrid search combining vector similarity and keyword matching.

        This method executes a sophisticated search that combines:
        - K-nearest neighbor (KNN) vector similarity search (70% weight)
        - Multi-field keyword search with fuzzy matching (30% weight)
        - Optional filtering and score thresholds
        - Aggregations for faceted search results

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

        # Parse optional filter expression (can be either A or B shape; see _coerce_filter_clauses)
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

        # Embed the query
        vec = self.embedding.embed_query(q)

        # Build filter clauses (accept both shapes)
        filter_clauses = self._coerce_filter_clauses(filter_obj)

        # Respect the tool's limit/threshold defaults
        limit = (filter_obj or {}).get("limit", self.number_of_results)
        score_threshold = (filter_obj or {}).get("score_threshold", 0)

        # Build the same hybrid body as your SearchService
        body = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "knn": {
                                self.vector_field: {
                                    "vector": vec,
                                    "k": 10,  # fixed to match the tool
                                    "boost": 0.7,
                                }
                            }
                        },
                        {
                            "multi_match": {
                                "query": q,
                                "fields": ["text^2", "filename^1.5"],
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                                "boost": 0.3,
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            },
            "aggs": {
                "data_sources": {"terms": {"field": "filename", "size": 20}},
                "document_types": {"terms": {"field": "mimetype", "size": 10}},
                "owners": {"terms": {"field": "owner", "size": 10}},
            },
            "_source": [
                "filename",
                "mimetype",
                "page",
                "text",
                "source_url",
                "owner",
                "allowed_users",
                "allowed_groups",
            ],
            "size": limit,
        }
        if filter_clauses:
            body["query"]["bool"]["filter"] = filter_clauses

        if isinstance(score_threshold, (int, float)) and score_threshold > 0:
            # top-level min_score (matches your tool)
            body["min_score"] = score_threshold

        resp = client.search(index=self.index_name, body=body)
        hits = resp.get("hits", {}).get("hits", [])
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

        This is the main interface method that performs the search using the
        configured search_query and returns results in Langflow's Data format.

        Returns:
            List of Data objects containing search results with text and metadata

        Raises:
            Exception: If search operation fails
        """
        try:
            raw = self.search(self.search_query or "")
            return [Data(text=hit["page_content"], **hit["metadata"]) for hit in raw]
            self.log(self.ingest_data)
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

                if is_basic:
                    build_config["jwt_token"]["value"] = ""

                return build_config

        except (KeyError, ValueError) as e:
            self.log(f"update_build_config error: {e}")

        return build_config
