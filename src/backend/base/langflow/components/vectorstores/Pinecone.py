from typing import List, Optional, Union

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from langchain_pinecone._utilities import DistanceStrategy
from langchain_pinecone.vectorstores import PineconeVectorStore

from langflow.custom import CustomComponent
from langflow.field_typing import Embeddings
from langflow.schema import Record


class PineconeComponent(CustomComponent):
    display_name = "Pinecone"
    description = "Construct Pinecone wrapper from raw documents."
    icon = "Pinecone"
    field_order = ["index_name", "namespace", "distance_strategy", "pinecone_api_key", "documents", "embedding"]

    def build_config(self):
        distance_options = [e.value.title().replace("_", " ") for e in DistanceStrategy]
        distance_value = distance_options[0]
        return {
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
            "embedding": {"display_name": "Embedding"},
            "index_name": {"display_name": "Index Name"},
            "namespace": {"display_name": "Namespace"},
            "text_key": {"display_name": "Text Key"},
            "distance_strategy": {
                "display_name": "Distance Strategy",
                # get values from enum
                # and make them title case for display
                "options": distance_options,
                "advanced": True,
                "value": distance_value,
            },
            "pinecone_api_key": {
                "display_name": "Pinecone API Key",
                "default": "",
                "password": True,
                "required": True,
            },
            "pool_threads": {
                "display_name": "Pool Threads",
                "default": 1,
                "advanced": True,
            },
        }

    def from_existing_index(
        self,
        index_name: str,
        embedding: Embeddings,
        pinecone_api_key: str | None,
        text_key: str = "text",
        namespace: Optional[str] = None,
        distance_strategy: DistanceStrategy = DistanceStrategy.COSINE,
        pool_threads: int = 4,
    ) -> PineconeVectorStore:
        """Load pinecone vectorstore from index name."""
        pinecone_index = PineconeVectorStore.get_pinecone_index(
            index_name, pool_threads, pinecone_api_key=pinecone_api_key
        )
        return PineconeVectorStore(
            index=pinecone_index,
            embedding=embedding,
            text_key=text_key,
            namespace=namespace,
            distance_strategy=distance_strategy,
        )

    def from_documents(
        self,
        documents: List[Document],
        embedding: Embeddings,
        index_name: str,
        pinecone_api_key: str | None,
        text_key: str = "text",
        namespace: Optional[str] = None,
        pool_threads: int = 4,
        distance_strategy: DistanceStrategy = DistanceStrategy.COSINE,
        batch_size: int = 32,
        upsert_kwargs: Optional[dict] = None,
        embeddings_chunk_size: int = 1000,
    ) -> PineconeVectorStore:
        """Create a new pinecone vectorstore from documents."""
        texts = [d.page_content for d in documents]
        metadatas = [d.metadata for d in documents]
        pinecone = self.from_existing_index(
            index_name=index_name,
            embedding=embedding,
            pinecone_api_key=pinecone_api_key,
            text_key=text_key,
            namespace=namespace,
            distance_strategy=distance_strategy,
            pool_threads=pool_threads,
        )
        pinecone.add_texts(
            texts,
            metadatas=metadatas,
            ids=None,
            namespace=namespace,
            batch_size=batch_size,
            embedding_chunk_size=embeddings_chunk_size,
            **(upsert_kwargs or {}),
        )
        return pinecone

    def build(
        self,
        embedding: Embeddings,
        distance_strategy: str,
        inputs: Optional[List[Record]] = None,
        text_key: str = "text",
        pool_threads: int = 4,
        index_name: Optional[str] = None,
        pinecone_api_key: Optional[str] = None,
        namespace: Optional[str] = "default",
    ) -> Union[VectorStore, BaseRetriever]:
        # get distance strategy from string
        distance_strategy = distance_strategy.replace(" ", "_").upper()
        _distance_strategy = DistanceStrategy[distance_strategy]
        if not index_name:
            raise ValueError("Index Name is required.")
        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        if documents:
            return self.from_documents(
                documents=documents,
                embedding=embedding,
                index_name=index_name,
                pinecone_api_key=pinecone_api_key,
                text_key=text_key,
                namespace=namespace,
                distance_strategy=_distance_strategy,
                pool_threads=pool_threads,
            )

        return self.from_existing_index(
            index_name=index_name,
            embedding=embedding,
            pinecone_api_key=pinecone_api_key,
            text_key=text_key,
            namespace=namespace,
            distance_strategy=_distance_strategy,
            pool_threads=pool_threads,
        )
