# ruff: noqa: TC002, TC003, ARG002, UP037, BLE001, S110
# TC002/TC003 — imports needed at runtime by eval_custom_component_code
# ARG002 — **kwargs required by LangChain VectorStore interface
# UP037 — quoted annotations needed because exec() ignores __future__
# BLE001/S110 — Docling export calls may fail unpredictably

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from contextlib import contextmanager, suppress
from typing import Any
from urllib.parse import unquote, urlparse

import psycopg2
import psycopg2.extras
import psycopg2.pool
import psycopg2.sql
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, SecretStrInput, StrInput
from lfx.schema.data import Data


def _safe_json_dumps(obj):
    return json.dumps(obj, default=str)


# Map distance strategy to the SQL operator used by openGauss DataVec
_DISTANCE_OPERATORS = {
    "COSINE": "<=>",
    "EUCLIDEAN": "<->",
    "INNER_PRODUCT": "<#>",
    "MANHATTAN": "<+>",
}

# Map distance strategy to the index operator class used by openGauss DataVec
_INDEX_OPERATORS = {
    "COSINE": "vector_cosine_ops",
    "EUCLIDEAN": "vector_l2_ops",
    "INNER_PRODUCT": "vector_ip_ops",
    "MANHATTAN": "vector_l1_ops",
}


class OpenGaussVectorStore(VectorStore):
    """openGauss DataVec vector store backed by psycopg2."""

    def __init__(
        self,
        embedding: Embeddings,
        *,
        host: str = "localhost",
        port: int = 5432,
        user: str = "gaussdb",
        password: str = "",
        database: str = "postgres",
        table_name: str = "public.langflow",
        embedding_dimension: int = 1536,
        index_type: str = "HNSW",
        distance_strategy: str = "COSINE",
        create_index: bool = False,
    ):
        self.embedding_function = embedding
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._table_name = table_name
        self._embedding_dimension = embedding_dimension
        self._index_type = index_type.upper()
        self._distance_strategy = distance_strategy.upper()
        self._create_index = create_index
        self._table_ident = self._build_table_ident()

        if self._index_type not in ("HNSW", "IVFFLAT"):
            msg = f"Unsupported index type: {self._index_type}. Use 'HNSW' or 'IVFFLAT'."
            raise ValueError(msg)
        if self._distance_strategy not in _DISTANCE_OPERATORS:
            msg = f"Unsupported distance strategy: {self._distance_strategy}. Use one of {list(_DISTANCE_OPERATORS)}."
            raise ValueError(msg)

        self._operator = _DISTANCE_OPERATORS[self._distance_strategy]
        self._index_operator = _INDEX_OPERATORS[self._distance_strategy]

        self._pool = psycopg2.pool.SimpleConnectionPool(
            1,
            5,
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            database=self._database,
        )
        self._create_table()

    def __del__(self) -> None:
        with suppress(Exception):
            self._pool.closeall()

    def _build_table_ident(self):
        if "." in self._table_name:
            schema, table = self._table_name.split(".", 1)
            return psycopg2.sql.SQL("{}.{}").format(
                psycopg2.sql.Identifier(schema),
                psycopg2.sql.Identifier(table),
            )
        return psycopg2.sql.Identifier(self._table_name)

    @contextmanager
    def _cursor(self):
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        finally:
            self._pool.putconn(conn)

    def _create_table(self) -> None:
        sql = psycopg2.sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                metadata JSONB,
                embedding vector({}) NOT NULL
            );
        """).format(self._table_ident, psycopg2.sql.Literal(self._embedding_dimension))
        with self._cursor() as cur:
            cur.execute(sql)

        if self._create_index:
            safe_name = self._table_name.replace(".", "_")
            index_name = f"idx_{safe_name}_embedding"
            with self._cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename = %s AND indexname = %s);",
                    (self._table_name, index_name),
                )
                exists = cur.fetchone()[0]

            if not exists:
                if self._index_type == "HNSW":
                    idx_sql = psycopg2.sql.SQL("""
                        CREATE INDEX IF NOT EXISTS {} ON {}
                        USING hnsw (embedding {}) WITH (m = 16, ef_construction = 64);
                    """).format(
                        psycopg2.sql.Identifier(index_name),
                        self._table_ident,
                        psycopg2.sql.Identifier(self._index_operator),
                    )
                else:
                    idx_sql = psycopg2.sql.SQL("""
                        CREATE INDEX IF NOT EXISTS {} ON {}
                        USING ivfflat (embedding {}) WITH (lists = 200);
                    """).format(
                        psycopg2.sql.Identifier(index_name),
                        self._table_ident,
                        psycopg2.sql.Identifier(self._index_operator),
                    )
                with self._cursor() as cur:
                    cur.execute(idx_sql)

    @property
    def embeddings(self) -> Embeddings:
        return self.embedding_function

    def add_texts(
        self, texts: Iterable[str], metadatas: list[dict] | None = None, *, ids: list[str] | None = None, **kwargs: Any
    ) -> list[str]:
        texts = list(texts)
        if metadatas is None:
            metadatas = [{} for _ in range(len(texts))]

        generated_ids = [str(uuid.uuid4()) for _ in range(len(texts))] if ids is None else list(ids)

        insert_sql = psycopg2.sql.SQL("""
            INSERT INTO {} (id, text, metadata, embedding) VALUES %s
            ON DUPLICATE KEY UPDATE text = VALUES(text), metadata = VALUES(metadata), embedding = VALUES(embedding);
        """).format(self._table_ident)

        batch_size = 20
        with self._cursor() as cur:
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i : i + batch_size]
                batch_metas = metadatas[i : i + batch_size]
                batch_ids = generated_ids[i : i + batch_size]
                batch_embeddings = self.embedding_function.embed_documents(batch_texts)
                records = [
                    (doc_id, text, _safe_json_dumps(meta), _safe_json_dumps(emb))
                    for doc_id, text, meta, emb in zip(
                        batch_ids, batch_texts, batch_metas, batch_embeddings, strict=False
                    )
                ]
                psycopg2.extras.execute_values(cur, insert_sql, records, template=None, page_size=100)

        return generated_ids

    def add_documents(self, documents: list[Document], **kwargs: Any) -> list[str]:
        metadatas = [doc.metadata for doc in documents]
        texts = [doc.page_content for doc in documents]

        if "ids" not in kwargs:
            ids = [doc.id if (hasattr(doc, "id") and doc.id is not None) else str(uuid.uuid4()) for doc in documents]
            kwargs["ids"] = tuple(ids)

        return self.add_texts(texts, metadatas, **kwargs)

    def similarity_search(self, query: str, k: int = 4, filters: dict | None = None, **kwargs: Any) -> list[Document]:
        embedding = self.embedding_function.embed_query(query)
        return self.similarity_search_by_vector(embedding, k=k, filters=filters)

    def similarity_search_by_vector(
        self, embedding: list[float], k: int = 4, filters: dict | None = None, **kwargs: Any
    ) -> list[Document]:
        with self._cursor() as cur:
            if filters is None:
                sql = psycopg2.sql.SQL("""
                    SELECT id, metadata, text, embedding {} %s AS distance
                    FROM {} ORDER BY distance LIMIT %s
                """).format(psycopg2.sql.SQL(self._operator), self._table_ident)
                cur.execute(sql, (_safe_json_dumps(embedding), k))
            else:
                sql = psycopg2.sql.SQL("""
                    SELECT id, metadata, text, embedding {} %s AS distance
                    FROM {} WHERE metadata @> %s::jsonb ORDER BY distance LIMIT %s
                """).format(psycopg2.sql.SQL(self._operator), self._table_ident)
                cur.execute(sql, (_safe_json_dumps(embedding), _safe_json_dumps(filters), k))

            return [Document(page_content=text, metadata=metadata, id=_id) for _id, metadata, text, _distance in cur]

    def delete(self, ids: list[str] | None = None, **kwargs: Any) -> bool | None:
        with self._cursor() as cur:
            if ids is None:
                cur.execute(psycopg2.sql.SQL("DELETE FROM {}").format(self._table_ident))
            else:
                cur.execute(psycopg2.sql.SQL("DELETE FROM {} WHERE id = ANY(%s)").format(self._table_ident), (ids,))
            return True

    @classmethod
    def from_documents(
        cls,
        documents: list[Document],
        embedding: Embeddings,
        **kwargs: Any,
    ) -> "OpenGaussVectorStore":
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        if "ids" not in kwargs:
            kwargs["ids"] = [
                doc.id if (hasattr(doc, "id") and doc.id is not None) else str(uuid.uuid4()) for doc in documents
            ]
        return cls.from_texts(texts, embedding, metadatas=metadatas, **kwargs)

    @classmethod
    def from_texts(
        cls,
        texts: list[str],
        embedding: Embeddings,
        metadatas: list[dict] | None = None,
        *,
        ids: list[str] | None = None,
        **kwargs: Any,
    ) -> "OpenGaussVectorStore":
        instance = cls(embedding=embedding, **kwargs)
        instance.add_texts(texts, metadatas, ids=ids)
        return instance


class OpenGaussVectorStoreComponent(LCVectorStoreComponent):
    display_name = "openGauss"
    description = "openGauss DataVec Vector Store with search capabilities"
    name = "opengauss"
    icon = "openGauss"

    inputs = [
        SecretStrInput(
            name="connection_string",
            display_name="openGauss Server Connection String",
            required=True,
        ),
        StrInput(name="table_name", display_name="Table", value="public.langflow", required=True),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"], required=True),
        BoolInput(
            name="create_index",
            display_name="Create Index",
            value=False,
            advanced=True,
            info="If enabled, a vector index will be created for faster search. "
            "Disable if index creation causes database issues.",
        ),
        DropdownInput(
            name="index_type",
            display_name="Index Type",
            options=["HNSW", "IVFFLAT"],
            value="HNSW",
            advanced=True,
        ),
        DropdownInput(
            name="distance_strategy",
            display_name="Distance Strategy",
            options=["COSINE", "EUCLIDEAN", "INNER_PRODUCT", "MANHATTAN"],
            value="COSINE",
            advanced=True,
        ),
        IntInput(
            name="embedding_dimension",
            display_name="Embedding Dimension",
            value=1536,
            advanced=True,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=3,
            advanced=True,
        ),
    ]

    def _build_kwargs(self) -> dict[str, Any]:
        parsed = urlparse(self.connection_string)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "user": unquote(parsed.username) if parsed.username else "gaussdb",
            "password": unquote(parsed.password) if parsed.password else "",
            "database": parsed.path.lstrip("/") or "postgres",
            "table_name": self.table_name,
            "embedding_dimension": self.embedding_dimension,
            "index_type": self.index_type,
            "distance_strategy": self.distance_strategy,
            "create_index": self.create_index,
        }

    @staticmethod
    def _extract_text(data_obj: Data) -> str:
        """Extract text from a Data object, trying multiple common keys."""
        for key in ("text", "content"):
            val = data_obj.data.get(key)
            if val:
                return str(val)

        # Handle Docling-style output: "doc" is a DoclingDocument object
        doc = data_obj.data.get("doc")
        if doc is not None and hasattr(doc, "export_to_text"):
            try:
                text = doc.export_to_text()
                if text:
                    return text
            except Exception:
                pass
        if doc is not None and hasattr(doc, "export_to_markdown"):
            try:
                text = doc.export_to_markdown()
                if text:
                    return text
            except Exception:
                pass

        return ""

    @check_cached_vector_store
    def build_vector_store(self) -> "OpenGaussVectorStore":
        self.ingest_data = self._prepare_ingest_data()
        kwargs = self._build_kwargs()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                doc = _input.to_lc_document()
                if not doc.page_content:
                    doc.page_content = self._extract_text(_input)
                if doc.page_content:
                    documents.append(doc)
            elif isinstance(_input, Document):
                if _input.page_content:
                    documents.append(_input)

        if documents:
            return OpenGaussVectorStore.from_documents(
                embedding=self.embedding,
                documents=documents,
                **kwargs,
            )

        return OpenGaussVectorStore(embedding=self.embedding, **kwargs)

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )
            data = docs_to_data(docs)
            self.status = data
            return data
        return []
