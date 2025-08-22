import os

import orjson
from astrapy.admin import parse_api_endpoint

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.inputs.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    HandleInput,
    IntInput,
    SecretStrInput,
    StrInput,
)
from lfx.schema.data import Data


class AstraDBGraphVectorStoreComponent(LCVectorStoreComponent):
    display_name: str = "Astra DB Graph"
    description: str = "Implementation of Graph Vector Store using Astra DB"
    name = "AstraDBGraph"
    icon: str = "AstraDB"

    inputs = [
        SecretStrInput(
            name="token",
            display_name="Astra DB Application Token",
            info="Authentication token for accessing Astra DB.",
            value="ASTRA_DB_APPLICATION_TOKEN",
            required=True,
            advanced=os.getenv("ASTRA_ENHANCED", "false").lower() == "true",
        ),
        SecretStrInput(
            name="api_endpoint",
            display_name="Database" if os.getenv("ASTRA_ENHANCED", "false").lower() == "true" else "API Endpoint",
            info="API endpoint URL for the Astra DB service.",
            value="ASTRA_DB_API_ENDPOINT",
            required=True,
        ),
        StrInput(
            name="collection_name",
            display_name="Collection Name",
            info="The name of the collection within Astra DB where the vectors will be stored.",
            required=True,
        ),
        StrInput(
            name="metadata_incoming_links_key",
            display_name="Metadata incoming links key",
            info="Metadata key used for incoming links.",
            advanced=True,
        ),
        *LCVectorStoreComponent.inputs,
        StrInput(
            name="keyspace",
            display_name="Keyspace",
            info="Optional keyspace within Astra DB to use for the collection.",
            advanced=True,
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding Model",
            input_types=["Embeddings"],
            info="Allows an embedding model configuration.",
        ),
        DropdownInput(
            name="metric",
            display_name="Metric",
            info="Optional distance metric for vector comparisons in the vector store.",
            options=["cosine", "dot_product", "euclidean"],
            value="cosine",
            advanced=True,
        ),
        IntInput(
            name="batch_size",
            display_name="Batch Size",
            info="Optional number of data to process in a single batch.",
            advanced=True,
        ),
        IntInput(
            name="bulk_insert_batch_concurrency",
            display_name="Bulk Insert Batch Concurrency",
            info="Optional concurrency level for bulk insert operations.",
            advanced=True,
        ),
        IntInput(
            name="bulk_insert_overwrite_concurrency",
            display_name="Bulk Insert Overwrite Concurrency",
            info="Optional concurrency level for bulk insert operations that overwrite existing data.",
            advanced=True,
        ),
        IntInput(
            name="bulk_delete_concurrency",
            display_name="Bulk Delete Concurrency",
            info="Optional concurrency level for bulk delete operations.",
            advanced=True,
        ),
        DropdownInput(
            name="setup_mode",
            display_name="Setup Mode",
            info="Configuration mode for setting up the vector store, with options like 'Sync', or 'Off'.",
            options=["Sync", "Off"],
            advanced=True,
            value="Sync",
        ),
        BoolInput(
            name="pre_delete_collection",
            display_name="Pre Delete Collection",
            info="Boolean flag to determine whether to delete the collection before creating a new one.",
            advanced=True,
            value=False,
        ),
        StrInput(
            name="metadata_indexing_include",
            display_name="Metadata Indexing Include",
            info="Optional list of metadata fields to include in the indexing.",
            advanced=True,
            list=True,
        ),
        StrInput(
            name="metadata_indexing_exclude",
            display_name="Metadata Indexing Exclude",
            info="Optional list of metadata fields to exclude from the indexing.",
            advanced=True,
            list=True,
        ),
        StrInput(
            name="collection_indexing_policy",
            display_name="Collection Indexing Policy",
            info='Optional JSON string for the "indexing" field of the collection. '
            "See https://docs.datastax.com/en/astra-db-serverless/api-reference/collections.html#the-indexing-option",
            advanced=True,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=4,
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            info="Search type to use",
            options=[
                "Similarity",
                "Similarity with score threshold",
                "MMR (Max Marginal Relevance)",
                "Graph Traversal",
                "MMR (Max Marginal Relevance) Graph Traversal",
            ],
            value="MMR (Max Marginal Relevance) Graph Traversal",
            advanced=True,
        ),
        FloatInput(
            name="search_score_threshold",
            display_name="Search Score Threshold",
            info="Minimum similarity score threshold for search results. "
            "(when using 'Similarity with score threshold')",
            value=0,
            advanced=True,
        ),
        DictInput(
            name="search_filter",
            display_name="Search Metadata Filter",
            info="Optional dictionary of filters to apply to the search query.",
            advanced=True,
            is_list=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self):
        try:
            from langchain_astradb import AstraDBGraphVectorStore
            from langchain_astradb.utils.astradb import SetupMode
        except ImportError as e:
            msg = (
                "Could not import langchain Astra DB integration package. "
                "Please install it with `pip install langchain-astradb`."
            )
            raise ImportError(msg) from e

        try:
            if not self.setup_mode:
                self.setup_mode = self._inputs["setup_mode"].options[0]

            setup_mode_value = SetupMode[self.setup_mode.upper()]
        except KeyError as e:
            msg = f"Invalid setup mode: {self.setup_mode}"
            raise ValueError(msg) from e

        try:
            self.log(f"Initializing Graph Vector Store {self.collection_name}")

            vector_store = AstraDBGraphVectorStore(
                embedding=self.embedding_model,
                collection_name=self.collection_name,
                metadata_incoming_links_key=self.metadata_incoming_links_key or "incoming_links",
                token=self.token,
                api_endpoint=self.api_endpoint,
                namespace=self.keyspace or None,
                environment=parse_api_endpoint(self.api_endpoint).environment if self.api_endpoint else None,
                metric=self.metric or None,
                batch_size=self.batch_size or None,
                bulk_insert_batch_concurrency=self.bulk_insert_batch_concurrency or None,
                bulk_insert_overwrite_concurrency=self.bulk_insert_overwrite_concurrency or None,
                bulk_delete_concurrency=self.bulk_delete_concurrency or None,
                setup_mode=setup_mode_value,
                pre_delete_collection=self.pre_delete_collection,
                metadata_indexing_include=[s for s in self.metadata_indexing_include if s] or None,
                metadata_indexing_exclude=[s for s in self.metadata_indexing_exclude if s] or None,
                collection_indexing_policy=orjson.loads(self.collection_indexing_policy.encode("utf-8"))
                if self.collection_indexing_policy
                else None,
            )
        except Exception as e:
            msg = f"Error initializing AstraDBGraphVectorStore: {e}"
            raise ValueError(msg) from e

        self.log(f"Vector Store initialized: {vector_store.astra_env.collection_name}")
        self._add_documents_to_vector_store(vector_store)

        return vector_store

    def _add_documents_to_vector_store(self, vector_store) -> None:
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                msg = "Vector Store Inputs must be Data objects."
                raise TypeError(msg)

        if documents:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            try:
                vector_store.add_documents(documents)
            except Exception as e:
                msg = f"Error adding documents to AstraDBGraphVectorStore: {e}"
                raise ValueError(msg) from e
        else:
            self.log("No documents to add to the Vector Store.")

    def _map_search_type(self) -> str:
        match self.search_type:
            case "Similarity":
                return "similarity"
            case "Similarity with score threshold":
                return "similarity_score_threshold"
            case "MMR (Max Marginal Relevance)":
                return "mmr"
            case "Graph Traversal":
                return "traversal"
            case "MMR (Max Marginal Relevance) Graph Traversal":
                return "mmr_traversal"
            case _:
                return "similarity"

    def _build_search_args(self):
        args = {
            "k": self.number_of_results,
            "score_threshold": self.search_score_threshold,
        }

        if self.search_filter:
            clean_filter = {k: v for k, v in self.search_filter.items() if k and v}
            if len(clean_filter) > 0:
                args["filter"] = clean_filter
        return args

    def search_documents(self, vector_store=None) -> list[Data]:
        if not vector_store:
            vector_store = self.build_vector_store()

        self.log("Searching for documents in AstraDBGraphVectorStore.")
        self.log(f"Search query: {self.search_query}")
        self.log(f"Search type: {self.search_type}")
        self.log(f"Number of results: {self.number_of_results}")

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            try:
                search_type = self._map_search_type()
                search_args = self._build_search_args()

                docs = vector_store.search(query=self.search_query, search_type=search_type, **search_args)

                # Drop links from the metadata. At this point the links don't add any value for building the
                # context and haven't been restored to json which causes the conversion to fail.
                self.log("Removing links from metadata.")
                for doc in docs:
                    if "links" in doc.metadata:
                        doc.metadata.pop("links")

            except Exception as e:
                msg = f"Error performing search in AstraDBGraphVectorStore: {e}"
                raise ValueError(msg) from e

            self.log(f"Retrieved documents: {len(docs)}")

            data = docs_to_data(docs)

            self.log(f"Converted documents to data: {len(data)}")

            self.status = data
            return data
        self.log("No search input provided. Skipping search.")
        return []

    def get_retriever_kwargs(self):
        search_args = self._build_search_args()
        return {
            "search_type": self._map_search_type(),
            "search_kwargs": search_args,
        }
