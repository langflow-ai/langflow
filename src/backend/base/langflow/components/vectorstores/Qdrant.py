from typing import List

from langchain_community.vectorstores import Qdrant
from langflow.base.vectorstores.model import LCVectorStoreComponent
from langflow.helpers.data import docs_to_data
from langflow.io import (
    DropdownInput,
    HandleInput,
    IntInput,
    StrInput,
    SecretStrInput,
    DataInput,
    MultilineInput,
)
from langflow.schema import Data
from langchain.embeddings.base import Embeddings


class QdrantVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Qdrant"
    description = "Qdrant Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/qdrant"
    icon = "Qdrant"

    inputs = [
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        StrInput(name="host", display_name="Host", value="localhost", advanced=True),
        IntInput(name="port", display_name="Port", value=6333, advanced=True),
        IntInput(name="grpc_port", display_name="gRPC Port", value=6334, advanced=True),
        SecretStrInput(name="api_key", display_name="API Key", advanced=True),
        StrInput(name="prefix", display_name="Prefix", advanced=True),
        IntInput(name="timeout", display_name="Timeout", advanced=True),
        StrInput(name="path", display_name="Path", advanced=True),
        StrInput(name="url", display_name="URL", advanced=True),
        DropdownInput(
            name="distance_func",
            display_name="Distance Function",
            options=["Cosine", "Euclidean", "Dot Product"],
            value="Cosine",
            advanced=True,
        ),
        StrInput(name="content_payload_key", display_name="Content Payload Key", value="page_content", advanced=True),
        StrInput(name="metadata_payload_key", display_name="Metadata Payload Key", value="metadata", advanced=True),
        MultilineInput(name="search_query", display_name="Search Query"),
        DataInput(
            name="ingest_data",
            display_name="Ingest Data",
            is_list=True,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    def build_vector_store(self) -> Qdrant:
        return self._build_qdrant()

    def _build_qdrant(self) -> Qdrant:
        qdrant_kwargs = {
            "collection_name": self.collection_name,
            "content_payload_key": self.content_payload_key,
            "metadata_payload_key": self.metadata_payload_key,
        }

        server_kwargs = {
            "host": self.host if self.host else None,
            "port": int(self.port),  # Garantir que port seja um inteiro
            "grpc_port": int(self.grpc_port),  # Garantir que grpc_port seja um inteiro
            "api_key": self.api_key,
            "prefix": self.prefix,
            "timeout": int(self.timeout) if self.timeout else None,  # Garantir que timeout seja um inteiro
            "path": self.path if self.path else None,
            "url": self.url if self.url else None,
        }

        server_kwargs = {k: v for k, v in server_kwargs.items() if v is not None}
        documents = []

        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if not isinstance(self.embedding, Embeddings):
            raise ValueError("Invalid embedding object")

        if documents:
            qdrant = Qdrant.from_documents(documents, embedding=self.embedding, **qdrant_kwargs)
        else:
            from qdrant_client import QdrantClient

            client = QdrantClient(**server_kwargs)
            qdrant = Qdrant(embeddings=self.embedding, client=client, **qdrant_kwargs)

        return qdrant

    def search_documents(self) -> List[Data]:
        vector_store = self._build_qdrant()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )

            data = docs_to_data(docs)
            self.status = data
            return data
        else:
            return []
