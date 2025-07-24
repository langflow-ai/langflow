import json
from copy import deepcopy
from typing import TYPE_CHECKING

from chromadb.config import Settings
from langchain_chroma import Chroma
from typing_extensions import override

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.base.vectorstores.utils import chroma_collection_to_data
from langflow.inputs.inputs import (
    BoolInput,
    DropdownInput,
    FloatInput,
    HandleInput,
    IntInput,
    NestedDictInput,
    StrInput,
)
from langflow.schema.data import Data

if TYPE_CHECKING:
    from langflow.schema.dataframe import DataFrame


class ChromaVectorStoreComponent(LCVectorStoreComponent):
    """Chroma Vector Store with search capabilities, including similarity+score and metadata filtering."""

    display_name: str = "Chroma DB"
    description: str = "Chroma Vector Store with search capabilities"
    name = "Chroma"
    icon = "Chroma"

    inputs = [
        StrInput(
            name="collection_name",
            display_name="Collection Name",
            value="langflow",
        ),
        StrInput(
            name="persist_directory",
            display_name="Persist Directory",
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        StrInput(
            name="chroma_server_cors_allow_origins",
            display_name="Server CORS Allow Origins",
            advanced=True,
        ),
        StrInput(
            name="chroma_server_host",
            display_name="Server Host",
            advanced=True,
        ),
        IntInput(
            name="chroma_server_http_port",
            display_name="Server HTTP Port",
            advanced=True,
        ),
        IntInput(
            name="chroma_server_grpc_port",
            display_name="Server gRPC Port",
            advanced=True,
        ),
        BoolInput(
            name="chroma_server_ssl_enabled",
            display_name="Server SSL Enabled",
            advanced=True,
        ),
        BoolInput(
            name="allow_duplicates",
            display_name="Allow Duplicates",
            advanced=True,
            info="If false, will not add documents that are already in the Vector Store.",
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["Similarity", "Similarity with Score", "MMR"],
            value="Similarity",
            advanced=True,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=10,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            advanced=True,
            info="Limit the number of records to compare when Allow Duplicates is False.",
        ),
        FloatInput(
            name="sim_threshold",
            display_name="Similarity Threshold",
            info=(
                "Minimum similarity score (0 to 1) to include a document. Only applies to "
                "'Similarity with Score' search."
            ),
            value=0.0,
            range_spec={"min": 0.0, "max": 1.0},
            advanced=True,
        ),
        NestedDictInput(
            name="search_filter",
            display_name="Metadata Filter",
            input_types=["Data"],
            info="Dictionary of metadata filter to refine search results.",
            tool_mode=True,
        ),
    ]

    @override
    def set_attributes(self, params: dict):
        super().set_attributes(params)
        raw_filter = params.get("search_filter", "")
        if raw_filter:
            try:
                self.advance_search_filter = raw_filter
            except json.JSONDecodeError as err:
                msg = "The metadata filter must be a valid JSON dictionary."
                raise ValueError(msg) from err
        else:
            self.advance_search_filter = None

    @override
    @check_cached_vector_store
    def build_vector_store(self) -> Chroma:
        """Builds the Chroma object."""
        try:
            from chromadb import Client
            from langchain_chroma import Chroma
        except ImportError as e:
            msg = "Could not import Chroma integration package. Please install it with `pip install langchain-chroma`."
            raise ImportError(msg) from e

        chroma_settings = None
        client = None
        if self.chroma_server_host:
            chroma_settings = Settings(
                chroma_server_cors_allow_origins=self.chroma_server_cors_allow_origins or [],
                chroma_server_host=self.chroma_server_host,
                chroma_server_http_port=self.chroma_server_http_port or None,
                chroma_server_grpc_port=self.chroma_server_grpc_port or None,
                chroma_server_ssl_enabled=self.chroma_server_ssl_enabled,
            )
            client = Client(settings=chroma_settings)

        persist_directory = self.resolve_path(self.persist_directory) if self.persist_directory is not None else None

        chroma = Chroma(
            persist_directory=persist_directory,
            client=client,
            embedding_function=self.embedding,
            collection_name=self.collection_name,
        )

        self._add_documents_to_vector_store(chroma)
        self.status = chroma_collection_to_data(chroma.get(limit=self.limit))
        return chroma

    def _add_documents_to_vector_store(self, vector_store: "Chroma") -> None:
        """Adds documents to the Vector Store."""
        ingest_data: list | Data | DataFrame = self.ingest_data
        if not ingest_data:
            self.status = ""
            return

        ingest_data = self._prepare_ingest_data()

        stored_documents_without_id = []
        if self.allow_duplicates:
            stored_data = []
        else:
            stored_data = chroma_collection_to_data(vector_store.get(limit=self.limit))
            for value in deepcopy(stored_data):
                del value.id
                stored_documents_without_id.append(value)

        documents = []
        for _input in ingest_data or []:
            if isinstance(_input, Data):
                if _input not in stored_documents_without_id:
                    documents.append(_input.to_lc_document())
            else:
                msg = "Vector Store Inputs must be Data objects."
                raise TypeError(msg)

        if documents and self.embedding is not None:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            vector_store.add_documents(documents)
        else:
            self.log("No documents to add to the Vector Store.")

    def search_documents(self) -> list[Data]:
        """Search for documents in the vector store, with optional score and metadata filter."""
        if self._cached_vector_store is not None:
            vs = self._cached_vector_store
        else:
            vs = self.build_vector_store()
            self._cached_vector_store = vs

        query = self.search_query
        if not query:
            self.status = ""
            return []

        mode = self.search_type
        k = self.number_of_results
        filt = self.advance_search_filter
        threshold = float(self.sim_threshold or 0.0)

        if mode == "Similarity with Score" and hasattr(vs, "similarity_search_with_relevance_scores"):
            docs_and_scores = vs.similarity_search_with_relevance_scores(query, k=k, filter=filt or None)
            results: list[Data] = []
            for doc, score in docs_and_scores:
                if score >= threshold:
                    data = Data(
                        metadata={**getattr(doc, "metadata", {})},
                        score={"score": score},
                        text=doc.page_content,
                    )
                    results.append(data)
            self.status = results
            return results

        if filt:
            self.log(f"Filter: {filt}")
        self.log(f"Search input: {query}")
        self.log(f"Search type: {mode}")
        self.log(f"Number of results: {k}")
        self.log(f"Similarity threshold: {threshold}")

        if mode.lower() in ["similarity", "mmr"] and hasattr(vs, "search"):
            search_args = {
                "query": query,
                "search_type": mode.lower(),
                "k": k,
            }
            if filt:
                search_args["filter"] = filt
            docs = vs.search(**search_args)
            data_list = [Data(metadata={**getattr(d, "metadata", {})}, text=d.page_content) for d in docs]
            self.status = data_list
            return data_list

        return super().search_documents()
