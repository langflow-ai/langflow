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
class OpenSearchHybridComponent(LCVectorStoreComponent):
    """OpenSearch hybrid search: KNN (k=10, boost=0.7) + multi_match (boost=0.3) with optional filters & min_score."""

    display_name: str = "OpenSearch (Hybrid)"
    name: str = "OpenSearchHybrid"
    icon: str = "OpenSearch"
    description: str = "Hybrid search: KNN + keyword, with optional filters, min_score, and aggregations."

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
            display_name="Ingestion Metadata",
            info="Key value pairs to be inserted into each ingested document.",
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
            advanced=True,
        ),
        StrInput(
            name="opensearch_url",
            display_name="OpenSearch URL",
            value="http://localhost:9200",
            info="URL for your OpenSearch cluster.",
        ),
        StrInput(
            name="index_name",
            display_name="Index Name",
            value="langflow",
            info="The index to search.",
        ),
        DropdownInput(
            name="engine",
            display_name="Engine",
            options=["jvector", "nmslib", "faiss", "lucene"],
            value="jvector",
            info="Vector search engine to use.",
            advanced=True,
        ),
        DropdownInput(
            name="space_type",
            display_name="Space Type",
            options=["l2", "l1", "cosinesimil", "linf", "innerproduct"],
            value="l2",
            info="Distance metric for vector similarity.",
            advanced=True,
        ),
        IntInput(
            name="ef_construction",
            display_name="EF Construction",
            value=512,
            info="Size of the dynamic list used during k-NN graph creation.",
            advanced=True,
        ),
        IntInput(
            name="m",
            display_name="M Parameter",
            value=16,
            info="Number of bidirectional links created for each new element.",
            advanced=True,
        ),
        *LCVectorStoreComponent.inputs,  # includes search_query, add_documents, etc.
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        StrInput(
            name="vector_field",
            display_name="Vector Field",
            value="chunk_embedding",
            advanced=True,
            info="Vector field used for KNN.",
        ),
        IntInput(
            name="number_of_results",
            display_name="Default Size (limit)",
            value=10,
            advanced=True,
            info="Default number of hits when no limit provided in filter_expression.",
        ),
        MultilineInput(
            name="filter_expression",
            display_name="Filter Expression (JSON)",
            value="",
            info=(
                "Optional JSON to control filters/limit/score threshold.\n"
                "Accepted shapes:\n"
                '1) {"filter": [ {"term": {"filename":"foo"}}, '
                '{"terms":{"owner":["u1","u2"]}} ], "limit": 10, "score_threshold": 1.6 }\n'
                '2) Context-style maps: {"data_sources":["fileA"], '
                '"document_types":["application/pdf"], "owners":["123"]}\n'
                "Placeholders with __IMPOSSIBLE_VALUE__ are ignored."
            ),
        ),
        # ----- Auth controls (dynamic) -----
        DropdownInput(
            name="auth_mode",
            display_name="Auth Mode",
            value="basic",
            options=["basic", "jwt"],
            info="Choose Basic (username/password) or JWT (Bearer token).",
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
            display_name="Password",
            value="admin",
            show=False,
        ),
        SecretStrInput(
            name="jwt_token",
            display_name="JWT Token",
            value="JWT",
            load_from_db=True,
            show=True,
            info="Paste a valid JWT (sent as a header).",
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
        BoolInput(name="use_ssl", display_name="Use SSL", value=True, advanced=True),
        BoolInput(
            name="verify_certs",
            display_name="Verify Certificates",
            value=False,
            advanced=True,
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
        """For Approximate k-NN Search, this is the default mapping to create index."""
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
        """Validate AOSS with the engine."""
        if is_aoss and engine not in {"nmslib", "faiss"}:
            msg = "Amazon OpenSearch Service Serverless only supports `nmslib` or `faiss` engines"
            raise ValueError(msg)

    def _is_aoss_enabled(self, http_auth: Any) -> bool:
        """Check if the service is http_auth is set as `aoss`."""
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
        """Bulk Ingest Embeddings into given index."""
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
        self.log(metadatas[i])
        helpers.bulk(client, requests, max_chunk_bytes=max_chunk_bytes)
        return return_ids

    # ---------- auth / client ----------
    def _build_auth_kwargs(self) -> dict[str, Any]:
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
            for item in self.docs_metadata:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    additional_metadata[item["key"]] = item["value"]

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
        """Accepts two formats of filters.

        A) {"filter":[ ...term/terms objects... ], "limit":..., "score_threshold":...}
        B) Context-style: {"data_sources":[...], "document_types":[...], "owners":[...]}
        Returns a list of OS filter clauses (term/terms), skipping placeholders and empty terms.
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
            clauses: list[dict] = []
            for f in raw or []:
                if "term" in f and isinstance(f["term"], dict) and not self._is_placeholder_term(f["term"]):
                    clauses.append(f)
                elif "terms" in f and isinstance(f["terms"], dict):
                    field, vals = next(iter(f["terms"].items()))
                    if isinstance(vals, list) and len(vals) > 0:
                        clauses.append(f)
            return clauses

        # Case B: convert context-style maps into clauses
        field_mapping = {
            "data_sources": "filename",
            "document_types": "mimetype",
            "owners": "owner",
        }
        clauses: list[dict] = []
        for k, values in filter_obj.items():
            if not isinstance(values, list):
                continue
            field = field_mapping.get(k, k)
            if len(values) == 0:
                # Match-nothing placeholder (kept to mirror your tool semantics)
                clauses.append({"term": {field: "__IMPOSSIBLE_VALUE__"}})
            elif len(values) == 1:
                if values[0] != "__IMPOSSIBLE_VALUE__":
                    clauses.append({"term": {field: values[0]}})
            else:
                clauses.append({"terms": {field: values}})
        return clauses

    # ---------- search (single hybrid path matching your tool) ----------
    def search(self, query: str | None = None) -> list[dict[str, Any]]:
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
        clauses = self._coerce_filter_clauses(filter_obj)

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
        if clauses:
            body["query"]["bool"]["filter"] = clauses

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
        try:
            raw = self.search(self.search_query or "")
            return [Data(text=hit["page_content"], **hit["metadata"]) for hit in raw]
            self.log(self.ingest_data)
        except Exception as e:
            self.log(f"search_documents error: {e}")
            raise

    # -------- dynamic UI handling (auth switch) --------
    async def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
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
