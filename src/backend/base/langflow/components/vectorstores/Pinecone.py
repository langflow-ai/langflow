from typing import List

from langchain_core.retrievers import BaseRetriever
from langchain_pinecone import Pinecone

from langflow.custom import Component
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, DropdownInput, HandleInput, IntInput, Output, SecretStrInput, StrInput
from langflow.schema import Data


class PineconeVectorStoreComponent(Component):
    display_name = "Pinecone"
    description = "Pinecone Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/pinecone"
    icon = "Pinecone"

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
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        StrInput(
            name="text_key",
            display_name="Text Key",
            info="Key in the record to use as text.",
            value="text",
            advanced=True,
        ),
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
        Output(display_name="Vector Store", name="vector_store", method="build_vector_store", output_type=Pinecone),
        Output(
            display_name="Base Retriever",
            name="base_retriever",
            method="build_base_retriever",
            output_type=BaseRetriever,
        ),
        Output(display_name="Search Results", name="search_results", method="search_documents"),
    ]

    def build_vector_store(self) -> Pinecone:
        return self._build_pinecone()

    def _build_pinecone(self) -> Pinecone:
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

        if self.add_to_vector_store:
            documents = []
            for _input in self.vector_store_inputs or []:
                if isinstance(_input, Data):
                    documents.append(_input.to_lc_document())
                else:
                    documents.append(_input)

            if documents:
                pinecone.add_documents(documents)

        return pinecone

    def search_documents(self) -> List[Data]:
        vector_store = self._build_pinecone()

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
