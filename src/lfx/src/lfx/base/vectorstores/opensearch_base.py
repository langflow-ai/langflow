"""Base class for OpenSearch vector store components."""

from __future__ import annotations

import json
import uuid
from typing import Any

from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import OpenSearchException

from lfx.log import logger


class OpenSearchClientMixin:
    """Mixin providing OpenSearch client and authentication utilities."""

    # These attributes should be defined by the component
    opensearch_url: str
    use_ssl: bool
    verify_certs: bool
    auth_mode: str
    username: str
    password: str
    jwt_token: str
    jwt_header: str
    bearer_prefix: bool

    def _build_auth_kwargs(self) -> dict[str, Any]:
        """Build authentication configuration for OpenSearch client.

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


class OpenSearchIndexMixin:
    """Mixin providing OpenSearch index management utilities."""

    index_name: str

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
                    "embedding_model": {"type": "keyword"},
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
            logger.error(msg)
            raise ValueError(msg)

    def _validate_aoss_with_engines(self, *, is_aoss: bool, engine: str) -> None:
        """Validate engine compatibility with Amazon OpenSearch Serverless (AOSS).

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

        if field_def.get("type") == "knn_vector":
            return field_def.get("dimension")

        nested_props = field_def.get("properties")
        if isinstance(nested_props, dict) and nested_props.get("type") == "knn_vector":
            return nested_props.get("dimension")

        return None


class OpenSearchSearchMixin:
    """Mixin providing OpenSearch search utilities."""

    index_name: str

    def _is_placeholder_term(self, term_obj: dict) -> bool:
        """Check if a term object contains placeholder values."""
        return any(v == "__IMPOSSIBLE_VALUE__" for v in term_obj.values())

    def _coerce_filter_clauses(self, filter_obj: dict | None) -> list[dict]:
        """Convert filter expressions into OpenSearch-compatible filter clauses.

        Args:
            filter_obj: Filter configuration dictionary or None

        Returns:
            List of OpenSearch filter clauses (term/terms objects)
        """
        if not filter_obj:
            return []

        if isinstance(filter_obj, str):
            try:
                filter_obj = json.loads(filter_obj)
            except json.JSONDecodeError:
                return []

        # Case A: explicit list/dict under "filter"
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
                context_clauses.append({"term": {field: "__IMPOSSIBLE_VALUE__"}})
            elif len(values) == 1:
                if values[0] != "__IMPOSSIBLE_VALUE__":
                    context_clauses.append({"term": {field: values[0]}})
            else:
                context_clauses.append({"terms": {field: values}})
        return context_clauses

    def _detect_available_models(self, client: OpenSearch, filter_clauses: list[dict] | None = None) -> list[str]:
        """Detect which embedding models have documents in the index.

        Args:
            client: OpenSearch client instance
            filter_clauses: Optional filter clauses to scope model detection

        Returns:
            List of embedding model names found in the index
        """
        try:
            agg_query = {"size": 0, "aggs": {"embedding_models": {"terms": {"field": "embedding_model", "size": 10}}}}

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
            return []
        else:
            return models


class OpenSearchBulkMixin:
    """Mixin providing OpenSearch bulk ingestion utilities."""

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
                "embedding_model": embedding_model,
                **metadata,
            }
            if is_aoss:
                request["id"] = _id
            else:
                request["_id"] = _id
            requests.append(request)
            return_ids.append(_id)

        helpers.bulk(client, requests, max_chunk_bytes=max_chunk_bytes)
        return return_ids


class OpenSearchBaseMixin(
    OpenSearchClientMixin,
    OpenSearchIndexMixin,
    OpenSearchSearchMixin,
    OpenSearchBulkMixin,
):
    """Combined mixin with all OpenSearch utilities."""

