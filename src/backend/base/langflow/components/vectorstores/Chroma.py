from copy import deepcopy
from typing import List, Optional, Union

import chromadb
from chromadb.config import Settings
from langchain.vectorstores import Chroma
from langchain.embeddings.base import Embeddings
from langchain.schema import BaseRetriever

from langflow.base.vectorstores.utils import chroma_collection_to_data
from langflow.custom import Component
from langflow.inputs import BoolInput, IntInput, StrInput, HandleInput, DropdownInput
from langflow.schema import Data
from langflow.template import Output
from langflow.field_typing import Embeddings
from langflow.helpers.data import docs_to_data

from loguru import logger

class ChromaVectorStoreComponent(Component):
    """
    Chroma Vector Store with search capabilities
    """

    display_name: str = "Chroma DB"
    description: str = "Chroma Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/chroma"
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
        StrInput(
            name="code",
            display_name="Code",
            advanced=True,
        ),
        StrInput(
            name="vector_store_inputs",
            display_name="Vector Store Inputs",
            input_types=["Document", "Data"],
            is_list=True
        ),
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"]
        ),
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
        BoolInput(
            name="add_to_vector_store",
            display_name="Add to Vector Store",
            info="If true, the Vector Store Inputs will be added to the Vector Store.",
        ),
        StrInput(
            name="search_input",
            display_name="Search Input",
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["Similarity", "MMR"],
            value="Similarity",
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=4,
        ),
    ]

    outputs = [
        Output(
            display_name="Vector Store",
            name="vector_store",
            method="build_vector_store",
        ),
        Output(
            display_name="Base Retriever",
            name="base_retriever",
            method="build_base_retriever",
        ),
        Output(
            display_name="Search Results",
            name="search_results",
            method="search_documents",
        ),
    ]

    def build_vector_store(self) -> Chroma:
        """
        Builds the Vector Store object.
        """
        return self._build_chroma()

    def build_base_retriever(self) -> BaseRetriever:
        """
        Builds the BaseRetriever object.
        """
        return self._build_chroma()

    def _build_chroma(self) -> Chroma:
        """
        Builds the Chroma object.
        """
        # Chroma settings
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
            client = chromadb.Client(settings=chroma_settings)

        # Check persist_directory and expand it if it is a relative path
        if self.persist_directory is not None:
            persist_directory = self.resolve_path(self.persist_directory)
        else:
            persist_directory = None

        chroma = Chroma(
            persist_directory=persist_directory,
            client=client,
            embedding_function=self.embedding,
            collection_name=self.collection_name,
        )

        if self.add_to_vector_store:
            self._add_documents_to_vector_store(chroma)

        self.status = chroma_collection_to_data(chroma.get())
        return chroma

    def _add_documents_to_vector_store(self, chroma: Chroma) -> None:
        """
        Adds documents to the Vector Store.
        """
        if self.allow_duplicates:
            stored_data = []
        else:
            stored_data = chroma_collection_to_data(chroma.get())
            _stored_documents_without_id = []
            for value in deepcopy(stored_data):
                del value.id
                _stored_documents_without_id.append(value)

        documents = []
        for _input in self.vector_store_inputs or []:
            if isinstance(_input, Data):
                if _input not in _stored_documents_without_id:
                    documents.append(_input.to_lc_document())
            else:
                raise ValueError("Vector Store Inputs must be Data objects.")

        if documents and self.embedding is not None:
            logger.debug(f"Adding {len(documents)} documents to the Vector Store.")
            chroma.add_documents(documents)
        else:
            logger.debug("No documents to add to the Vector Store.")

    def search_documents(self) -> List[Data]:
        """
        Search for documents in the Chroma vector store.
        """
        if not self.search_input:
            return

        vector_store = self._build_chroma()

        logger.debug(f"Search input: {self.search_input}")
        logger.debug(f"Search type: {self.search_type}")
        logger.debug(f"Number of results: {self.number_of_results}")

        if self.search_input and isinstance(self.search_input, str) and self.search_input.strip():
            if self.search_type == "Similarity":
                docs = vector_store.similarity_search(
                    query=self.search_input,
                    k=self.number_of_results,
                )
            elif self.search_type == "MMR":
                docs = vector_store.max_marginal_relevance_search(
                    query=self.search_input,
                    k=self.number_of_results,
                )
            else:
                raise ValueError(f"Invalid search type: {self.search_type}")

            logger.debug(f"Retrieved documents: {len(docs)}")

            data = docs_to_data(docs)
            logger.debug(f"Converted documents to data: {len(data)}")
            self.status = data
            return data
        else:
            logger.debug("No search input provided. Skipping search.")
            return []
