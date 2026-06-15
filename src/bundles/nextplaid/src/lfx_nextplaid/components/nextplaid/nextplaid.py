from __future__ import annotations

import base64
import hashlib
import io
from typing import Any

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.io import (
    BoolInput,
    DropdownInput,
    FloatInput,
    HandleInput,
    IntInput,
    Output,
    StrInput,
)
from lfx.schema.data import Data


class NextPlaidVectorStoreComponent(LCVectorStoreComponent):
    """NextPlaid multi-vector (ColBERT/ColPali-style) vector store."""

    display_name: str = "NextPlaid"
    description: str = (
        "Multi-vector (ColBERT/PLAID) vector store backed by NextPlaid. "
        "Supports text retrieval via ColBERT models and image retrieval via "
        "ColPali models. Connect a vLLM Multivector Embeddings component."
    )
    name = "NextPlaid"
    icon = "NextPlaid"

    inputs = [
        StrInput(
            name="url",
            display_name="Server URL",
            value="http://localhost:8080",
            info="Base URL of the running NextPlaid server.",
        ),
        StrInput(
            name="index_name",
            display_name="Index Name",
            value="langflow",
            info="Name of the index to create or connect to.",
        ),
        DropdownInput(
            name="nbits",
            display_name="Quantization Bits",
            options=["2", "4"],
            value="4",
            info="Bit-width for PLAID quantization. 4-bit gives better quality.",
            advanced=True,
        ),
        BoolInput(
            name="create_index_if_not_exists",
            display_name="Create Index If Not Exists",
            value=True,
            advanced=True,
        ),
        FloatInput(
            name="write_timeout",
            display_name="Write Timeout (seconds)",
            value=30.0,
            info=(
                "Seconds to wait for each batch to finish indexing. "
                "0 = async (search may return empty on first run). "
                "Recommended: 30+ when ingesting and searching in the same flow run."
            ),
            advanced=True,
        ),
        IntInput(
            name="index_batch_size",
            display_name="Index Batch Size",
            value=500,
            advanced=True,
            info=(
                "Documents per indexing request. PLAID builds its initial cluster "
                "centroids from the first batch — larger batches produce better "
                "retrieval quality. Approximate limits per 1GB request: "
                "~26,000 text docs (ColBERT-small, 96-dim), "
                "~2,000 PDF pages (ColPali, 1000-patch x 128-dim)."
            ),
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(
            name="embedding",
            display_name="Embedding (Multivector)",
            input_types=["Embeddings"],
            info=(
                "Connect a vLLM Multivector Embeddings component. "
                "For image indexing, the model must support embed_images() "
                "(requires a ColPali model such as ModernVBERT/colmodernvbert)."
            ),
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return from similarity search.",
            value=4,
            advanced=True,
        ),
    ]

    # Declared explicitly (rather than inherited from LCVectorStoreComponent) so the
    # static extension validator can resolve the component's output methods; mirrors
    # the base outputs and keeps the search output usable as an agent tool.
    outputs = [
        Output(
            display_name="Search Results",
            name="search_results",
            method="search_documents",
            tool_mode=True,
        ),
        Output(
            display_name="Table",
            name="dataframe",
            method="as_dataframe",
        ),
    ]

    @staticmethod
    def _data_to_pil(item: Data):
        """Extract a PIL Image from a Data object produced by PdfPagesToImages."""
        from PIL import Image as PILImage

        b64 = item.data.get("base64_image", "")
        if not b64:
            msg = f"Data object with content_type '{item.data.get('content_type')}' has no 'base64_image' field."
            raise ValueError(msg)
        return PILImage.open(io.BytesIO(base64.b64decode(b64)))

    @staticmethod
    def _stable_image_id(item: Data, index_name: str, position: int) -> str:
        """Derive a stable upsert ID from available metadata."""
        return (
            item.data.get("document_id")
            or hashlib.sha256(
                f"{index_name}:{item.data.get('source', '')}:{item.data.get('page', position)}".encode()
            ).hexdigest()
        )

    @check_cached_vector_store
    def build_vector_store(self):
        try:
            from langchain_plaid.vectorstores import NextPlaidVectorStore as LangchainNextPlaid
        except ImportError as e:
            msg = "Could not import langchain-plaid. Install it with: pip install langchain-plaid"
            raise ImportError(msg) from e

        if self.embedding is None:
            msg = (
                "No embedding model connected. Connect a vLLM Multivector Embeddings component to the Embedding input."
            )
            raise ValueError(msg)

        nextplaid_store = LangchainNextPlaid(
            url=self.url,
            index_name=self.index_name,
            embedding=self.embedding,
            nbits=int(self.nbits),
            create_index_if_not_exists=self.create_index_if_not_exists,
            write_timeout=self.write_timeout,
        )

        self.ingest_data = self._prepare_ingest_data()

        # Flatten — Langflow wraps ingest data in a list: [[doc1, doc2, ...]]
        raw_inputs: list[Any] = []
        for item in self.ingest_data or []:
            if isinstance(item, list):
                raw_inputs.extend(item)
            else:
                raw_inputs.append(item)

        if not raw_inputs:
            return nextplaid_store

        # Route items into text documents or images.
        # A Data object is treated as an image when it carries content_type: image/*
        # (set by PdfPagesToImages). Everything else is a text document.
        text_docs = []
        image_data_items: list[Data] = []  # Data objects wrapping images
        raw_image_items: list[Any] = []  # raw PIL Images (advanced usage)

        for item in raw_inputs:
            if isinstance(item, Data):
                if item.data.get("content_type", "").startswith("image/"):
                    image_data_items.append(item)
                else:
                    doc = item.to_lc_document()
                    if doc.id is None:
                        doc.id = (
                            doc.metadata.get("document_id")
                            or doc.metadata.get("doc_id")
                            or doc.metadata.get("id")
                            or hashlib.sha256((doc.page_content or "").strip().encode("utf-8")).hexdigest()
                        )
                    text_docs.append(doc)
            else:
                # Raw PIL Image passed directly (e.g. from a custom component)
                raw_image_items.append(item)

        batch_size = max(self.index_batch_size or 500, 1)

        # ── Text ingestion ────────────────────────────────────────────────────
        if text_docs:
            for i in range(0, len(text_docs), batch_size):
                nextplaid_store.add_documents(text_docs[i : i + batch_size])

        # ── Image ingestion from Data objects (PdfPagesToImages output) ───────
        if image_data_items:
            if not hasattr(self.embedding, "embed_images"):
                msg = (
                    f"{type(self.embedding).__name__} does not implement embed_images()."
                    " Use a ColPali-compatible model (e.g. ModernVBERT/colmodernvbert)."
                )
                raise TypeError(msg)

            for i in range(0, len(image_data_items), batch_size):
                batch = image_data_items[i : i + batch_size]

                pil_images = [self._data_to_pil(item) for item in batch]
                metadatas = [{k: v for k, v in item.data.items() if k != "base64_image"} for item in batch]
                ids = [self._stable_image_id(item, self.index_name, i + j) for j, item in enumerate(batch)]
                nextplaid_store.add_images(pil_images, metadatas=metadatas, ids=ids)

        # ── Raw PIL image ingestion (advanced / programmatic use) ─────────────
        if raw_image_items:
            if not hasattr(self.embedding, "embed_images"):
                msg = (
                    f"{type(self.embedding).__name__} does not implement embed_images()."
                    " Use a ColPali-compatible model (e.g. ModernVBERT/colmodernvbert)."
                )
                raise TypeError(msg)

            for i in range(0, len(raw_image_items), batch_size):
                batch = raw_image_items[i : i + batch_size]
                ids = [
                    hashlib.sha256(f"{self.index_name}:raw_image:{i + j}".encode()).hexdigest()
                    for j in range(len(batch))
                ]
                nextplaid_store.add_images(batch, ids=ids)

        return nextplaid_store

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
