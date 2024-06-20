from typing import List

from langchain_community.vectorstores import MongoDBAtlasVectorSearch
from langchain_core.retrievers import BaseRetriever

from langflow.custom import Component
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, HandleInput, IntInput, Output, StrInput
from langflow.schema import Data


class MongoVectorStoreComponent(Component):
    display_name = "MongoDB Atlas"
    description = "MongoDB Atlas Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/mongodb_atlas"
    icon = "MongoDB"

    inputs = [
        StrInput(name="mongodb_atlas_cluster_uri", display_name="MongoDB Atlas Cluster URI", required=True),
        StrInput(name="db_name", display_name="Database Name", required=True),
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        StrInput(name="index_name", display_name="Index Name", required=True),
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
        Output(
            display_name="Vector Store",
            name="vector_store",
            method="build_vector_store",
            output_type=MongoDBAtlasVectorSearch,
        ),
        Output(
            display_name="Base Retriever",
            name="base_retriever",
            method="build_base_retriever",
            output_type=BaseRetriever,
        ),
        Output(display_name="Search Results", name="search_results", method="search_documents"),
    ]

    def build_vector_store(self) -> MongoDBAtlasVectorSearch:
        return self._build_mongodb_atlas()

    def _build_mongodb_atlas(self) -> MongoDBAtlasVectorSearch:
        try:
            from pymongo import MongoClient
        except ImportError:
            raise ImportError("Please install pymongo to use MongoDB Atlas Vector Store")

        try:
            mongo_client: MongoClient = MongoClient(self.mongodb_atlas_cluster_uri)
            collection = mongo_client[self.db_name][self.collection_name]
        except Exception as e:
            raise ValueError(f"Failed to connect to MongoDB Atlas: {e}")

        if self.add_to_vector_store:
            documents = []
            for _input in self.vector_store_inputs or []:
                if isinstance(_input, Data):
                    documents.append(_input.to_lc_document())
                else:
                    documents.append(_input)

            if documents:
                vector_store = MongoDBAtlasVectorSearch.from_documents(
                    documents=documents,
                    embedding=self.embedding,
                    collection=collection,
                    db_name=self.db_name,
                    index_name=self.index_name,
                    mongodb_atlas_cluster_uri=self.mongodb_atlas_cluster_uri,
                )
            else:
                vector_store = MongoDBAtlasVectorSearch(
                    embedding=self.embedding,
                    collection=collection,
                    index_name=self.index_name,
                )
        else:
            vector_store = MongoDBAtlasVectorSearch(
                embedding=self.embedding,
                collection=collection,
                index_name=self.index_name,
            )

        return vector_store

    def search_documents(self) -> List[Data]:
        vector_store = self._build_mongodb_atlas()

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
