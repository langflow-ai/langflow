from __future__ import annotations

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.io import (
    BoolInput,
    DropdownInput,
    FloatInput,
    HandleInput,
    IntInput,
    StrInput,
)
from lfx.schema.data import Data


class NextPlaidVectorStoreComponent(LCVectorStoreComponent):
    """NextPlaid multi-vector (ColBERT-style) store with search capabilities."""

    display_name: str = "NextPlaid"
    description: str = "NextPlaid multi-vector (ColBERT/PLAID) vector store with semantic search capabilities"
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
            info="Bit-width for PLAID quantization (2 or 4).",
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
                "Seconds to wait for indexing to complete before searching. "
                "0 = async (fire-and-forget, search may return empty). "
                "Set to 30+ when ingesting and searching in the same flow run."
            ),
            advanced=True,
        ),
        IntInput(
            name="index_batch_size",
            display_name="Index Batch Size",
            value=500,
            advanced=True,
            info=(
                "Number of documents per indexing request. "
                "NextPlaid supports ~1GB per request. "
                "Larger batches produce better initial PLAID clusters. "
                "Set as high as your network allows."
            ),
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(
            name="embedding",
            display_name="Embedding (ColBERT-compatible)",
            input_types=["Embeddings"],
            info=(
                "Must implement the multi-vector contract: "
                "embed_documents -> List[List[List[float]]], "
                "embed_query -> List[List[float]]."
            ),
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self):
        try:
            from langchain_plaid.vectorstores import NextPlaidVectorStore as LangchainNextPlaid
        except ImportError as e:
            msg = "Could not import langchain-plaid. Install it with: pip install langchain-plaid"
            raise ImportError(msg) from e

        if self.embedding is None:
            msg = "No embedding model connected. Connect a VllmColBERTEmbeddingsComponent to the Embedding input."
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

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            nextplaid_store.add_documents(documents)

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
