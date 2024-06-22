from typing import List

from langchain_community.vectorstores import Qdrant
from langchain_core.retrievers import BaseRetriever

from langflow.custom import Component
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, DropdownInput, HandleInput, IntInput, Output, SecretStrInput, StrInput
from langflow.schema import Data


class QdrantVectorStoreComponent(Component):
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
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        HandleInput(
            name="vector_store_inputs",
            display_name="Vector Store Inputs",
            input_types=["Document", "Data"],
            is_list=True,
        ),
        BoolInput(
            name="add_to_vector_store",
            display_name="Add to Vector Store",
            info="If true, the Vector Store Inputs will be added to the Vector Store.",
        ),
        StrInput(name="search_input", display_name="Search Input"),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Vector Store", name="vector_store", method="build_vector_store", output_type=Qdrant),
        Output(
            display_name="Base Retriever",
            name="base_retriever",
            method="build_base_retriever",
            output_type=BaseRetriever,
        ),
        Output(display_name="Search Results", name="search_results", method="search_documents"),
    ]

    def build_vector_store(self) -> Qdrant:
        return self._build_qdrant()

    def _build_qdrant(self) -> Qdrant:
        qdrant_kwargs = {
            "collection_name": self.collection_name,
            "content_payload_key": self.content_payload_key,
            "distance_func": self.distance_func,
            "metadata_payload_key": self.metadata_payload_key,
        }

        server_kwargs = {
            "host": self.host,
            "port": self.port,
            "grpc_port": self.grpc_port,
            "api_key": self.api_key,
            "prefix": self.prefix,
            "timeout": self.timeout,
            "path": self.path,
            "url": self.url,
        }

        # Remove None values from server_kwargs
        server_kwargs = {k: v for k, v in server_kwargs.items() if v is not None}

        if self.add_to_vector_store:
            documents = []
            for _input in self.vector_store_inputs or []:
                if isinstance(_input, Data):
                    documents.append(_input.to_lc_document())
                else:
                    documents.append(_input)

            if documents:
                qdrant = Qdrant.from_documents(
                    documents, embedding=self.embedding, client_kwargs=server_kwargs, **qdrant_kwargs
                )
            else:
                from qdrant_client import QdrantClient

                client = QdrantClient(**server_kwargs)
                qdrant = Qdrant(embedding_function=self.embedding.embed_query, client=client, **qdrant_kwargs)
        else:
            from qdrant_client import QdrantClient

            client = QdrantClient(**server_kwargs)
            qdrant = Qdrant(embedding_function=self.embedding.embed_query, client=client, **qdrant_kwargs)

        return qdrant

    def search_documents(self) -> List[Data]:
        vector_store = self._build_qdrant()

        if self.search_input and isinstance(self.search_input, str) and self.search_input.strip():
            docs = vector_store.similarity_search(
                query=self.search_input,
                k=self.number_of_results,
            )

            data = docs_to_data(docs)
            self.status = data
            return data
        else:
            return []
