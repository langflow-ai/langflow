"""OpenSearch Vector Store Component with Multi-Model Hybrid Search."""

from __future__ import annotations

import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from opensearchpy.exceptions import RequestError

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.base.vectorstores.opensearch_base import OpenSearchBaseMixin
from lfx.base.vectorstores.opensearch_utils import (
    build_embedding_identifiers,
    build_embedding_info_string,
    get_embedding_field_name,
    get_embedding_model_name_from_obj,
)
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection

if TYPE_CHECKING:
    from opensearchpy import OpenSearch
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MultilineInput, SecretStrInput, StrInput, TableInput
from lfx.log import logger
from lfx.schema.data import Data


@vector_store_connection
class OpenSearchVectorStoreComponentMultimodalMultiEmbedding(LCVectorStoreComponent, OpenSearchBaseMixin):
    """OpenSearch Vector Store Component with Multi-Model Hybrid Search Capabilities.

    This component provides vector storage and retrieval using OpenSearch, combining semantic
    similarity search (KNN) with keyword-based search for optimal results.

    Features:
    - Multi-model vector storage with dynamic fields (chunk_embedding_{model_name})
    - Hybrid search combining multiple KNN queries (dis_max) + keyword matching
    - Auto-detection of available models in the index
    - Parallel query embedding generation for all detected models
    - Vector storage with configurable engines (jvector, nmslib, faiss, lucene)
    - Flexible authentication (Basic auth, JWT tokens)
    """

    display_name: str = "OpenSearch (Multi-Model Multi-Embedding)"
    icon: str = "OpenSearch"
    description: str = (
        "Store and search documents using OpenSearch with multi-model hybrid semantic and keyword search."
    )

    default_keys: list[str] = [
        "opensearch_url",
        "index_name",
        *[i.name for i in LCVectorStoreComponent.inputs],
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
            info="Additional metadata key-value pairs to be added to all ingested documents.",
            table_schema=[
                {"name": "key", "display_name": "Key", "type": "str", "description": "Key name"},
                {"name": "value", "display_name": "Value", "type": "str", "description": "Value of the metadata"},
            ],
            value=[],
            input_types=["Data"],
        ),
        StrInput(
            name="opensearch_url",
            display_name="OpenSearch URL",
            value="http://localhost:9200",
            info="The connection URL for your OpenSearch cluster.",
        ),
        StrInput(
            name="index_name",
            display_name="Index Name",
            value="langflow",
            info="The OpenSearch index name where documents will be stored and searched.",
        ),
        DropdownInput(
            name="engine",
            display_name="Vector Engine",
            options=["jvector", "nmslib", "faiss", "lucene"],
            value="jvector",
            info="Vector search engine. Note: Amazon OpenSearch Serverless only supports 'nmslib' or 'faiss'.",
            advanced=True,
        ),
        DropdownInput(
            name="space_type",
            display_name="Distance Metric",
            options=["l2", "l1", "cosinesimil", "linf", "innerproduct"],
            value="l2",
            info="Distance metric for calculating vector similarity.",
            advanced=True,
        ),
        IntInput(
            name="ef_construction",
            display_name="EF Construction",
            value=512,
            info="Size of the dynamic candidate list during index construction.",
            advanced=True,
        ),
        IntInput(
            name="m",
            display_name="M Parameter",
            value=16,
            info="Number of bidirectional connections for each vector in the HNSW graph.",
            advanced=True,
        ),
        IntInput(
            name="num_candidates",
            display_name="Candidate Pool Size",
            value=1000,
            info="Number of approximate neighbors to consider for each KNN query. Set to 0 to disable.",
            advanced=True,
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"], is_list=True),
        StrInput(
            name="embedding_model_name",
            display_name="Embedding Model Name",
            value="",
            info="Name of the embedding model to use for ingestion. Leave empty to use the first embedding.",
            advanced=False,
        ),
        StrInput(
            name="vector_field",
            display_name="Legacy Vector Field Name",
            value="chunk_embedding",
            advanced=True,
            info="Legacy field name for backward compatibility.",
        ),
        IntInput(
            name="number_of_results",
            display_name="Default Result Limit",
            value=10,
            advanced=True,
            info="Default maximum number of search results to return.",
        ),
        MultilineInput(
            name="filter_expression",
            display_name="Search Filters (JSON)",
            value="",
            info="Optional JSON configuration for search filtering, result limits, and score thresholds.",
        ),
        DropdownInput(
            name="auth_mode",
            display_name="Authentication Mode",
            value="basic",
            options=["basic", "jwt"],
            info="Authentication method: 'basic' for username/password or 'jwt' for JWT token.",
            real_time_refresh=True,
            advanced=False,
        ),
        StrInput(name="username", display_name="Username", value="admin", show=True),
        SecretStrInput(name="password", display_name="OpenSearch Password", value="admin", show=True),
        SecretStrInput(
            name="jwt_token",
            display_name="JWT Token",
            value="JWT",
            load_from_db=False,
            show=False,
            info="Valid JSON Web Token for authentication.",
        ),
        StrInput(name="jwt_header", display_name="JWT Header Name", value="Authorization", show=False, advanced=True),
        BoolInput(name="bearer_prefix", display_name="Prefix 'Bearer '", value=True, show=False, advanced=True),
        BoolInput(
            name="use_ssl",
            display_name="Use SSL/TLS",
            value=True,
            advanced=True,
            info="Enable SSL/TLS encryption for secure connections.",
        ),
        BoolInput(
            name="verify_certs",
            display_name="Verify SSL Certificates",
            value=False,
            advanced=True,
            info="Verify SSL certificates when connecting.",
        ),
    ]

    def _get_embedding_model_name(self, embedding_obj=None) -> str:
        """Get the embedding model name from component config or embedding object."""
        if hasattr(self, "embedding_model_name") and self.embedding_model_name:
            return self.embedding_model_name.strip()

        name = get_embedding_model_name_from_obj(embedding_obj)
        if name:
            return name

        if hasattr(self, "embedding") and self.embedding:
            embeddings = self.embedding if isinstance(self.embedding, list) else [self.embedding]
            if embeddings:
                name = get_embedding_model_name_from_obj(embeddings[0])
                if name:
                    return name

        msg = "Could not determine embedding model name. Please set the 'embedding_model_name' field."
        raise ValueError(msg)

    @check_cached_vector_store
    def build_vector_store(self) -> OpenSearch:
        """Build and return the OpenSearch client as vector store."""
        client = self.build_client()

        has_search_query = bool((self.search_query or "").strip())
        if not has_search_query:
            logger.debug("Ingestion-only mode activated: search operations will be skipped")

        logger.warning(f"Embedding: {self.embedding}")
        self._add_documents_to_vector_store(client=client)
        return client

    def _add_documents_to_vector_store(self, client: OpenSearch) -> None:
        """Process and ingest documents into the OpenSearch vector store."""
        logger.debug("[INGESTION] _add_documents_to_vector_store called")
        self.ingest_data = self._prepare_ingest_data()

        docs = self.ingest_data or []
        if not docs:
            logger.debug("Ingestion complete: No documents provided")
            return

        if not self.embedding:
            msg = "Embedding handle is required to embed documents."
            raise ValueError(msg)

        embeddings_list = self.embedding if isinstance(self.embedding, list) else [self.embedding]
        embeddings_list = [e for e in embeddings_list if e is not None]

        if not embeddings_list:
            logger.warning("All embeddings returned None (fail-safe mode). Skipping ingestion.")
            self.log("Embedding returned None (fail-safe mode). Skipping ingestion.")
            return

        self.log(f"Available embedding models: {len(embeddings_list)}")

        # Select embedding for ingestion
        selected_embedding, embedding_model = self._select_embedding_for_ingestion(embeddings_list)
        if not selected_embedding:
            return

        dynamic_field_name = get_embedding_field_name(embedding_model)
        logger.info(f"Selected embedding model for ingestion: '{embedding_model}'")
        self.log(f"Using embedding model: {embedding_model}, field: {dynamic_field_name}")

        # Extract texts and metadata
        texts, metadatas = self._extract_texts_and_metadata(docs)

        # Generate embeddings with retries
        vectors = self._generate_embeddings_with_retry(selected_embedding, texts, embedding_model)
        if not vectors:
            return

        # Ingest into OpenSearch
        self._ingest_vectors(client, vectors, texts, metadatas, dynamic_field_name, embedding_model)

    def _select_embedding_for_ingestion(self, embeddings_list: list) -> tuple[Any, str]:
        """Select the appropriate embedding for ingestion."""
        if hasattr(self, "embedding_model_name") and self.embedding_model_name and self.embedding_model_name.strip():
            target = self.embedding_model_name.strip()
            self.log(f"Looking for embedding model: {target}")

            for emb_obj in embeddings_list:
                possible_names = build_embedding_identifiers(emb_obj)
                available_models_attr = getattr(emb_obj, "available_models", None)

                if target in possible_names:
                    is_in_available = (
                        available_models_attr
                        and isinstance(available_models_attr, dict)
                        and target in available_models_attr
                    )
                    if is_in_available:
                        self.log(f"Found dedicated instance for '{target}' in available_models dict")
                        return available_models_attr[target], target
                    self.log(f"Found matching embedding model: {self._get_embedding_model_name(emb_obj)}")
                    return emb_obj, self._get_embedding_model_name(emb_obj)

            # Not found - build error message
            available_info = [build_embedding_info_string(emb, idx) for idx, emb in enumerate(embeddings_list)]
            msg = (
                f"Embedding model '{target}' not found.\n\n"
                f"Available embeddings:\n" + "\n".join(available_info) + "\n\n"
                "Set 'embedding_model_name' to one of the values above or leave empty."
            )
            raise ValueError(msg)

        # Use first embedding
        selected = embeddings_list[0]
        model_name = self._get_embedding_model_name(selected)
        self.log(f"Using first embedding: {model_name}")
        return selected, model_name

    def _extract_texts_and_metadata(self, docs: list) -> tuple[list[str], list[dict]]:
        """Extract texts and metadata from documents."""
        texts = []
        metadatas = []

        # Process docs_metadata table
        additional_metadata = {}
        if hasattr(self, "docs_metadata") and self.docs_metadata:
            if isinstance(self.docs_metadata[-1], Data):
                self.docs_metadata = self.docs_metadata[-1].data
                additional_metadata.update(self.docs_metadata)
            else:
                for item in self.docs_metadata:
                    if isinstance(item, dict) and "key" in item and "value" in item:
                        additional_metadata[item["key"]] = item["value"]

        for key, value in additional_metadata.items():
            if value == "None":
                additional_metadata[key] = None

        for doc_obj in docs:
            data_copy = json.loads(doc_obj.model_dump_json())
            text = data_copy.pop(doc_obj.text_key, doc_obj.default_value)
            texts.append(text)
            data_copy.update(additional_metadata)
            metadatas.append(data_copy)

        return texts, metadatas

    def _generate_embeddings_with_retry(
        self, embedding_obj, texts: list[str], model_name: str, max_attempts: int = 3
    ) -> list[list[float]] | None:
        """Generate embeddings with retry logic."""

        def embed_chunk(chunk_text: str) -> list[float]:
            return embedding_obj.embed_documents([chunk_text])[0]

        vectors: list[list[float]] | None = None
        delay = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                max_workers = min(max(len(texts), 1), 8)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(embed_chunk, chunk): idx for idx, chunk in enumerate(texts)}
                    vectors = [None] * len(texts)
                    for future in as_completed(futures):
                        idx = futures[future]
                        vectors[idx] = future.result()
            except Exception as exc:
                if attempt >= max_attempts:
                    logger.error(f"Embedding generation failed for {model_name} after retries: {exc}")
                    raise
                logger.warning(f"Embedding failed for {model_name} (attempt {attempt}/{max_attempts}), retrying...")
                time.sleep(delay)
                delay = min(delay * 2, 8.0)
            else:
                return vectors

        return None

    def _ingest_vectors(
        self,
        client: OpenSearch,
        vectors: list[list[float]],
        texts: list[str],
        metadatas: list[dict],
        field_name: str,
        embedding_model: str,
    ) -> None:
        """Ingest vectors into OpenSearch."""
        dim = len(vectors[0]) if vectors else 768

        auth_kwargs = self._build_auth_kwargs()
        is_aoss = self._is_aoss_enabled(auth_kwargs.get("http_auth"))

        engine = getattr(self, "engine", "jvector")
        self._validate_aoss_with_engines(is_aoss=is_aoss, engine=engine)

        space_type = getattr(self, "space_type", "l2")
        ef_construction = getattr(self, "ef_construction", 512)
        m = getattr(self, "m", 16)

        mapping = self._default_text_mapping(
            dim=dim, engine=engine, space_type=space_type, ef_construction=ef_construction, m=m, vector_field=field_name
        )

        # Ensure index exists
        try:
            if not client.indices.exists(index=self.index_name):
                self.log(f"Creating index '{self.index_name}'")
                client.indices.create(index=self.index_name, body=mapping)
        except RequestError as e:
            if e.error != "resource_already_exists_exception":
                logger.warning(f"Failed to create index '{self.index_name}': {e}")

        self._ensure_embedding_field_mapping(
            client, self.index_name, field_name, dim, engine, space_type, ef_construction, m
        )

        self.log(f"Indexing {len(texts)} documents with model '{embedding_model}'...")
        return_ids = self._bulk_ingest_embeddings(
            client,
            self.index_name,
            vectors,
            texts,
            metadatas,
            vector_field=field_name,
            text_field="text",
            embedding_model=embedding_model,
            mapping=mapping,
            is_aoss=is_aoss,
        )
        logger.info(f"Ingestion complete: {len(return_ids)} documents with model '{embedding_model}'")
        self.log(f"Successfully indexed {len(return_ids)} documents.")

    def search(self, query: str | None = None) -> list[dict[str, Any]]:
        """Perform multi-model hybrid search."""
        client = self.build_client()
        q = (query or "").strip()

        # Parse filters
        filter_obj = None
        if getattr(self, "filter_expression", "") and self.filter_expression.strip():
            try:
                filter_obj = json.loads(self.filter_expression)
            except json.JSONDecodeError as e:
                msg = f"Invalid filter_expression JSON: {e}"
                raise ValueError(msg) from e

        if not self.embedding:
            msg = "Embedding is required to run hybrid search."
            raise ValueError(msg)

        if self.embedding is None or (isinstance(self.embedding, list) and all(e is None for e in self.embedding)):
            logger.error("Embedding returned None. Cannot perform search.")
            return []

        filter_clauses = self._coerce_filter_clauses(filter_obj)
        available_models = self._detect_available_models(client, filter_clauses)

        if not available_models:
            logger.warning("No embedding models found in index, using current model")
            available_models = [self._get_embedding_model_name()]

        # Build embedding map and generate query embeddings
        embeddings_list = self.embedding if isinstance(self.embedding, list) else [self.embedding]
        embeddings_list = [e for e in embeddings_list if e is not None]

        if not embeddings_list:
            logger.error("No valid embeddings available. Cannot perform search.")
            return []

        embedding_by_model = self._build_embedding_model_map(embeddings_list)
        query_embeddings, matched_models, unmatched_models = self._generate_query_embeddings(
            q, available_models, embedding_by_model
        )

        self.log(f"[SEARCH] Models in index: {available_models}")
        self.log(f"[SEARCH] Available identifiers: {list(embedding_by_model.keys())}")
        self.log(f"[SUMMARY] Matched: {len(matched_models)}, Unmatched: {len(unmatched_models)}")

        if not query_embeddings:
            available_keys = list(embedding_by_model.keys())
            msg = f"Failed to generate embeddings. Index models: {available_models}, Available: {available_keys}"
            self.log(f"[FAIL] {msg}")
            raise ValueError(msg)

        # Build and execute search
        return self._execute_hybrid_search(
            client, q, query_embeddings, filter_clauses, filter_obj, available_models, matched_models
        )

    def _build_embedding_model_map(self, embeddings_list: list) -> dict[str, Any]:
        """Build a map of model names to embedding objects."""
        embedding_by_model = {}

        for emb_obj in embeddings_list:
            available_models = getattr(emb_obj, "available_models", None)

            # Map available_models dict entries
            if available_models and isinstance(available_models, dict):
                for model_key, dedicated_emb in available_models.items():
                    if model_key and str(model_key).strip():
                        model_str = str(model_key).strip()
                        if model_str not in embedding_by_model:
                            embedding_by_model[model_str] = dedicated_emb

            # Map traditional identifiers
            for identifier in build_embedding_identifiers(emb_obj):
                if identifier not in embedding_by_model:
                    embedding_by_model[identifier] = emb_obj

        return embedding_by_model

    def _generate_query_embeddings(
        self, query: str, available_models: list[str], embedding_by_model: dict[str, Any]
    ) -> tuple[dict[str, list[float]], list[str], list[str]]:
        """Generate query embeddings for all matched models."""
        query_embeddings = {}
        matched_models = []
        unmatched_models = []

        for model_name in available_models:
            try:
                if model_name in embedding_by_model:
                    emb_obj = embedding_by_model[model_name]
                    vec = emb_obj.embed_query(query)
                    query_embeddings[model_name] = vec
                    matched_models.append(model_name)
                    logger.info(f"Generated embedding for model: {model_name} (dims: {len(vec)})")
                    self.log(f"[MATCH] Model '{model_name}' - {len(vec)}-dim embedding")
                else:
                    unmatched_models.append(model_name)
                    logger.warning(f"No matching embedding for '{model_name}'")
                    self.log(f"[NO MATCH] Model '{model_name}'")
            except (RuntimeError, ValueError, ConnectionError, TimeoutError, AttributeError, KeyError) as e:
                logger.warning(f"Failed to generate embedding for {model_name}: {e}")
                self.log(f"[ERROR] Embedding failed for '{model_name}': {e}")

        return query_embeddings, matched_models, unmatched_models

    def _execute_hybrid_search(
        self,
        client: OpenSearch,
        query: str,
        query_embeddings: dict[str, list[float]],
        filter_clauses: list[dict],
        filter_obj: dict | None,
        available_models: list[str],
        matched_models: list[str],
    ) -> list[dict[str, Any]]:
        """Execute the hybrid search query."""
        index_properties = self._get_index_properties(client)
        legacy_vector_field = getattr(self, "vector_field", "chunk_embedding")

        # Build KNN queries
        embedding_fields = []
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
            vector_dim = len(embedding_vector)

            if not self._is_knn_vector_field(index_properties, field_name):
                self.log(f"[SKIP] Field '{field_name}' not knn_vector - skipping '{model_name}'")
                continue

            field_dim = self._get_field_dimension(index_properties, field_name)
            if field_dim is not None and field_dim != vector_dim:
                self.log(f"[DIM MISMATCH] '{model_name}': query={vector_dim} vs field={field_dim}")
                continue

            embedding_fields.append(field_name)
            base_query = {"knn": {field_name: {"vector": embedding_vector, "k": 50}}}

            if use_num_candidates:
                query_with_candidates = copy.deepcopy(base_query)
                query_with_candidates["knn"][field_name]["num_candidates"] = num_candidates
            else:
                query_with_candidates = base_query

            knn_queries_with_candidates.append(query_with_candidates)
            knn_queries_without_candidates.append(base_query)

        if not knn_queries_with_candidates:
            self.log(f"[WARN] No valid KNN queries. Embeddings: {list(query_embeddings.keys())}")
            return []

        # Build query body
        limit = (filter_obj or {}).get("limit", self.number_of_results)
        score_threshold = (filter_obj or {}).get("score_threshold", 0)

        exists_filter = {
            "bool": {"should": [{"exists": {"field": f}} for f in set(embedding_fields)], "minimum_should_match": 1}
        }

        body = {
            "query": {
                "bool": {
                    "should": [
                        {"dis_max": {"tie_breaker": 0.0, "boost": 0.7, "queries": knn_queries_with_candidates}},
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["text^2", "filename^1.5"],
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                                "boost": 0.3,
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                    "filter": [*filter_clauses, exists_filter],
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

        model_count = len(knn_queries_with_candidates)
        model_keys = list(query_embeddings.keys())
        logger.info(f"Executing hybrid search with {model_count} models: {model_keys}")
        self.log(f"[EXEC] Search with {len(knn_queries_with_candidates)} KNN queries, limit={limit}")
        self.log(f"[EXEC] Models: {list(query_embeddings.keys())}")
        self.log(f"[EXEC] Fields: {embedding_fields}")

        try:
            resp = client.search(index=self.index_name, body=body, params={"terminate_after": 0})
        except RequestError as e:
            resp = self._handle_search_error(
                e,
                client,
                body,
                knn_queries_without_candidates,
                query_embeddings,
                legacy_vector_field,
                filter_clauses,
                use_num_candidates=use_num_candidates,
                num_candidates=num_candidates,
            )

        hits = resp.get("hits", {}).get("hits", [])
        logger.info(f"Found {len(hits)} results")
        self.log(f"[RESULT] {len(hits)} results found")

        if len(hits) == 0:
            self.log(f"[EMPTY] models={available_models}, matched={matched_models}, fields={embedding_fields}")

        return [
            {
                "page_content": hit["_source"].get("text", ""),
                "metadata": {k: v for k, v in hit["_source"].items() if k != "text"},
                "score": hit.get("_score"),
            }
            for hit in hits
        ]

    def _handle_search_error(
        self,
        error: RequestError,
        client: OpenSearch,
        body: dict,
        knn_queries_without_candidates: list,
        query_embeddings: dict,
        legacy_field: str,
        filter_clauses: list,
        *,
        use_num_candidates: bool,
        num_candidates: int,
    ) -> dict:
        """Handle search request errors with fallback strategies."""
        error_message = str(error).lower()

        if use_num_candidates and "num_candidates" in error_message:
            logger.warning("Retrying without num_candidates parameter")
            fallback_body = copy.deepcopy(body)
            fallback_body["query"]["bool"]["should"][0]["dis_max"]["queries"] = knn_queries_without_candidates
            return client.search(index=self.index_name, body=fallback_body, params={"terminate_after": 0})

        if "knn_vector" in error_message or ("field" in error_message and "knn" in error_message):
            fallback_vector = next(iter(query_embeddings.values()), None)
            if fallback_vector is None:
                raise error
            logger.warning(f"Falling back to legacy field '{legacy_field}'")
            fallback_body = copy.deepcopy(body)
            fallback_body["query"]["bool"]["filter"] = filter_clauses
            knn_fallback = {"knn": {legacy_field: {"vector": fallback_vector, "k": 50}}}
            if use_num_candidates:
                knn_fallback["knn"][legacy_field]["num_candidates"] = num_candidates
            fallback_body["query"]["bool"]["should"][0]["dis_max"]["queries"] = [knn_fallback]
            return client.search(index=self.index_name, body=fallback_body, params={"terminate_after": 0})

        raise error

    def search_documents(self) -> list[Data]:
        """Search documents and return results as Data objects."""
        try:
            logger.info(f"Search query: {self.search_query}")
            if self._cached_vector_store is None:
                self.build_vector_store()

            search_query = (self.search_query or "").strip()
            if not search_query:
                self.log("No search query - ingestion completed, returning empty results")
                return []

            raw = self.search(search_query)
            return [Data(text=hit["page_content"], **hit["metadata"]) for hit in raw]
        except Exception as e:
            self.log(f"search_documents error: {e}")
            raise

    async def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Dynamically update component configuration based on field changes."""
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

        except (KeyError, ValueError) as e:
            self.log(f"update_build_config error: {e}")

        return build_config
