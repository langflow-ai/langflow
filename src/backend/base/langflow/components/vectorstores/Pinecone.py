from typing import List

from langchain_pinecone import Pinecone

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


class PineconeVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Pinecone"
    description = "Pinecone Vector Store with search capabilities"
    documentation = "https://python.langchain.com/v0.2/docs/integrations/vectorstores/pinecone/"
    name = "Pinecone"
    icon = "Pinecone"
    pinecone_instance = None

    inputs = [
        StrInput(name="index_name", display_name="Index Name", required=True),
        StrInput(name="namespace", display_name="Namespace", info="Namespace for the index."),
        DropdownInput(
            name="distance_strategy",
            display_name="Distance Strategy",
            options=["Cosine", "Euclidean", "Dot Product"],
            value="Cosine",
            advanced=True,
        ),
        SecretStrInput(name="pinecone_api_key", display_name="Pinecone API Key", required=True),
        StrInput(
            name="text_key",
            display_name="Text Key",
            info="Key in the record to use as text.",
            value="text",
            advanced=True,
        ),
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

    def build_vector_store(self) -> Pinecone:
        return self._build_pinecone()

    def _build_pinecone(self) -> Pinecone:
        if self.pinecone_instance is not None:
            return self.pinecone_instance
        from langchain_pinecone._utilities import DistanceStrategy
        from langchain_pinecone.vectorstores import Pinecone

        distance_strategy = self.distance_strategy.replace(" ", "_").upper()
        _distance_strategy = DistanceStrategy[distance_strategy]

        pinecone = Pinecone(
            index_name=self.index_name,
            embedding=self.embedding,
            text_key=self.text_key,
            namespace=self.namespace,
            distance_strategy=_distance_strategy,
            pinecone_api_key=self.pinecone_api_key,
        )

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            pinecone.add_documents(documents)
        self.pinecone_instance = pinecone
        return pinecone

    def search_documents(self) -> List[Data]:
        vector_store = self._build_pinecone()

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
