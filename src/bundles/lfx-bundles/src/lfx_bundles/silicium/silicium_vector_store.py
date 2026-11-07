# SPDX-License-Identifier: MIT
"""Silicium Zero-Copy In-Process Vector Store Component for Langflow (`lfx_bundles.silicium`)."""

from __future__ import annotations

import math
from typing import Any, Final

from lfx_bundles.silicium.silicium_semantic_cache import (
    NATIVE_CACHE_BACKEND,
    _derive_deterministic_embedding,
    _l2_distance_squared,
)

try:
    from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
    from lfx.helpers.data import docs_to_data
    from lfx.io import DropdownInput, HandleInput, IntInput, StrInput
    from lfx.schema.data import Data
except ImportError:
    from lfx_bundles.silicium.silicium_pii_guardrail import (
        Component as LCVectorStoreComponent,  # type: ignore[assignment]
    )
    from lfx_bundles.silicium.silicium_pii_guardrail import (
        Data,
        DropdownInput,
        IntInput,
        StrInput,
    )

    HandleInput = StrInput  # type: ignore[misc,assignment]

    def check_cached_vector_store(f: Any) -> Any:
        """Fallback decorator preserving `is_cached_vector_store_checked` metadata."""

        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            """Execute the wrapped `build_vector_store` method."""
            return f(self, *args, **kwargs)

        wrapper.is_cached_vector_store_checked = True  # type: ignore[attr-defined]
        return wrapper

    def docs_to_data(docs: list[Any]) -> list[Data]:
        """Convert document objects into Langflow `Data` records."""
        out: list[Data] = []
        for d in docs:
            text = getattr(d, "page_content", None) or getattr(d, "text", str(d))
            meta = getattr(d, "metadata", {}) or {}
            out.append(Data(data={"text": text, **dict(meta)}))
        return out


_NORM_EPSILON: Final[float] = 1e-12


class _SimpleDocument:
    """Minimal document record storing `page_content` and `metadata`."""

    def __init__(self, page_content: str, metadata: dict[str, Any] | None = None) -> None:
        """Initialize document text and metadata dictionary."""
        self.page_content = str(page_content)
        self.metadata: dict[str, Any] = dict(metadata or {})


class _InMemorySiliciumVectorStore:
    """Lightweight in-process vector store compatible with LangChain `similarity_search`."""

    def __init__(
        self,
        collection_name: str = "silicium_default",
        embedding: Any = None,
        dim: int = 16,
        distance_metric: str = "cosine",
    ) -> None:
        """Initialize the in-memory vector collection, embedding provider, and distance metric."""
        self.collection_name = collection_name
        self.embedding = embedding
        self.dim = max(8, int(dim))
        metric = str(distance_metric or "cosine").strip().lower()
        self.distance_metric = metric if metric in {"cosine", "l2"} else "cosine"
        self.engine_backend = NATIVE_CACHE_BACKEND
        self._records: list[tuple[list[float], _SimpleDocument]] = []

    @staticmethod
    def _coerce_vector(vec: Any) -> list[float]:
        """Validate and convert an embedding sequence into a non-empty `list[float]`."""
        if hasattr(vec, "encode") or hasattr(vec, "decode"):
            msg = "Configured embedding returned an invalid non-numeric sequence."
            raise ValueError(msg)
        try:
            floats = [float(x) for x in vec]
        except TypeError as exc:
            msg = "Configured embedding returned a non-iterable value."
            raise ValueError(msg) from exc
        if not floats:
            msg = "Configured embedding returned an empty vector."
            raise ValueError(msg)
        return floats

    def _embed_text(self, text: str) -> list[float]:
        """Compute an embedding vector using the configured provider or deterministic projection."""
        if self.embedding is not None:
            if not hasattr(self.embedding, "embed_query"):
                msg = "Configured embedding object does not implement 'embed_query'."
                raise ValueError(msg)
            return self._coerce_vector(self.embedding.embed_query(text))
        return _derive_deterministic_embedding(text, dim=self.dim)

    def add_documents(self, documents: list[Any]) -> None:
        """Embed and append documents into the vector store, preferring batch `embed_documents` when available."""
        if not documents:
            return
        parsed_docs: list[tuple[str, dict[str, Any]]] = []
        for doc in documents:
            if isinstance(doc, Data):
                content = str(getattr(doc, "text", "") or doc.data.get("text", ""))
                meta = dict(doc.data)
            else:
                content = str(getattr(doc, "page_content", None) or getattr(doc, "text", str(doc)))
                meta = dict(getattr(doc, "metadata", {}) or {})
            meta.setdefault("engine_backend", self.engine_backend)
            parsed_docs.append((content, meta))

        embed_docs_fn = getattr(self.embedding, "embed_documents", None) if self.embedding is not None else None
        if callable(embed_docs_fn):
            raw_vectors = list(embed_docs_fn([c for c, _ in parsed_docs]))
            if len(raw_vectors) != len(parsed_docs):
                msg = "Configured embedding 'embed_documents' returned a mismatched number of vectors."
                raise ValueError(msg)
            vectors = [self._coerce_vector(v) for v in raw_vectors]
        else:
            vectors = [self._embed_text(c) for c, _ in parsed_docs]

        for (content, meta), vec in zip(parsed_docs, vectors, strict=True):
            if self._records and len(vec) != len(self._records[0][0]):
                msg = f"Embedding dimension mismatch: expected={len(self._records[0][0])}, got={len(vec)}."
                raise ValueError(msg)
            self._records.append((vec, _SimpleDocument(page_content=content, metadata=meta)))

    def similarity_search(self, query: str, k: int = 4) -> list[_SimpleDocument]:
        """Return the top-`k` documents ranked by cosine similarity or negative squared L2 distance."""
        if not self._records:
            return []
        q_vec = self._embed_text(query)
        eff_k = max(1, int(k))
        scored: list[tuple[float, int, _SimpleDocument]] = []
        for idx, (vec, doc) in enumerate(self._records):
            if len(q_vec) != len(vec):
                msg = f"Embedding dimension mismatch: query={len(q_vec)}, stored={len(vec)}."
                raise ValueError(msg)
            n = len(vec)
            if self.distance_metric == "l2":
                score = -_l2_distance_squared(q_vec, vec)
            else:
                dot = sum(q_vec[i] * vec[i] for i in range(n))
                na = math.sqrt(sum(x * x for x in q_vec))
                nb = math.sqrt(sum(x * x for x in vec))
                score = (dot / (na * nb)) if (na > _NORM_EPSILON and nb > _NORM_EPSILON) else 0.0
            scored.append((score, -idx, doc))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored[:eff_k]]


class SiliciumVectorStoreComponent(LCVectorStoreComponent):
    """In-process Cosine and L2 Top-K Vector Store component with optional native C-ABI acceleration."""

    display_name = "Silicium Vector Store"
    description = (
        "In-memory Cosine and L2 Top-K vector store with deterministic fallback projection "
        "and optional native C-ABI distance acceleration."
    )
    documentation = "https://github.com/silicium369-spec/silicium-ai-ops"
    icon = "Silicium"
    name = "SiliciumVectorStoreComponent"

    inputs = [
        StrInput(
            name="collection_name",
            display_name="Collection Name",
            info="Name of the in-process Silicium vector collection.",
            value="silicium_collection",
        ),
        DropdownInput(
            name="distance_metric",
            display_name="Distance Metric",
            info="Similarity metric used for Top-K retrieval.",
            options=["cosine", "l2"],
            value="cosine",
            advanced=True,
        ),
        *getattr(LCVectorStoreComponent, "inputs", []),
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"],
            value=None,
            required=False,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Maximum Top-K results to return.",
            value=4,
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> _InMemorySiliciumVectorStore:
        """Build and populate the in-process Silicium vector store."""
        col_name = str(getattr(self, "collection_name", "silicium_collection") or "silicium_collection")
        metric = str(getattr(self, "distance_metric", "cosine") or "cosine")
        raw_emb = getattr(self, "embedding", None)
        emb = None if raw_emb in (None, "") else raw_emb
        store = _InMemorySiliciumVectorStore(
            collection_name=col_name,
            embedding=emb,
            distance_metric=metric,
        )

        if hasattr(self, "_prepare_ingest_data"):
            ingest_items = self._prepare_ingest_data()
        else:
            ingest_items = getattr(self, "ingest_data", None) or []

        docs: list[Any] = []
        for item in ingest_items or []:
            if hasattr(item, "to_lc_document"):
                docs.append(item.to_lc_document())
            else:
                docs.append(item)
        if docs:
            store.add_documents(docs)
        return store

    def search_documents(self) -> list[Data]:
        """Run bounded Top-K similarity search on the Silicium vector store."""
        store = self.build_vector_store()
        query = getattr(self, "search_query", "")
        k = max(1, int(getattr(self, "number_of_results", 4) or 4))
        if isinstance(query, str) and query.strip():
            docs = store.similarity_search(query=query.strip(), k=k)
            return docs_to_data(docs)
        return []
