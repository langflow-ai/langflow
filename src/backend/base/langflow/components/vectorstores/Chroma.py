from copy import deepcopy
from typing import TYPE_CHECKING

from chromadb.config import Settings
from langchain_chroma.vectorstores import Chroma
from loguru import logger

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.base.vectorstores.utils import chroma_collection_to_data
from langflow.io import BoolInput, DataInput, DropdownInput, HandleInput, IntInput, StrInput, MultilineInput
from langflow.schema import Data

if TYPE_CHECKING:
    from langchain_chroma import Chroma


class ChromaVectorStoreComponent(LCVectorStoreComponent):
    """
    Chroma Vector Store with search capabilities
    """

    display_name: str = "Chroma DB"
    description: str = "Chroma Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/chroma"
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
        MultilineInput(
            name="search_query",
            display_name="Search Query",
        ),
        DataInput(
            name="ingest_data",
            display_name="Ingest Data",
            is_list=True,
        ),
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
            options=["Similarity", "MMR"],
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
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> Chroma:
        """
        Builds the Chroma object.
        """
        try:
            from chromadb import Client
            from langchain_chroma import Chroma
        except ImportError:
            raise ImportError(
                "Could not import Chroma integration package. " "Please install it with `pip install langchain-chroma`."
            )
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
            client = Client(settings=chroma_settings)

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

        self._add_documents_to_vector_store(chroma)
        self.status = chroma_collection_to_data(chroma.get(limit=self.limit))
        return chroma

    def _add_documents_to_vector_store(self, vector_store: "Chroma") -> None:
        """
        Adds documents to the Vector Store.
        """
        if not self.ingest_data:
            self.status = ""
            return

        _stored_documents_without_id = []
        if self.allow_duplicates:
            stored_data = []
        else:
            stored_data = chroma_collection_to_data(vector_store.get(limit=self.limit))
            for value in deepcopy(stored_data):
                del value.id
                _stored_documents_without_id.append(value)

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                if _input not in _stored_documents_without_id:
                    documents.append(_input.to_lc_document())
            else:
                raise ValueError("Vector Store Inputs must be Data objects.")

        if documents and self.embedding is not None:
            logger.debug(f"Adding {len(documents)} documents to the Vector Store.")
            vector_store.add_documents(documents)
        else:
            logger.debug("No documents to add to the Vector Store.")
