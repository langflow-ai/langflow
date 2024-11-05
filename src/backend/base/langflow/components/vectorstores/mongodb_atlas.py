from langchain_community.vectorstores import MongoDBAtlasVectorSearch

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import DataInput, HandleInput, IntInput, MultilineInput, SecretStrInput, StrInput
from langflow.schema import Data


class MongoVectorStoreComponent(LCVectorStoreComponent):
    display_name = "MongoDB Atlas"
    description = "MongoDB Atlas Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/mongodb_atlas"
    name = "MongoDBAtlasVector"
    icon = "MongoDB"

    inputs = [
        SecretStrInput(name="mongodb_atlas_cluster_uri", display_name="MongoDB Atlas Cluster URI", required=True),
        StrInput(name="db_name", display_name="Database Name", required=True),
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        StrInput(name="index_name", display_name="Index Name", required=True),
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

    @check_cached_vector_store
    def build_vector_store(self) -> MongoDBAtlasVectorSearch:
        try:
            from pymongo import MongoClient
        except ImportError as e:
            msg = "Please install pymongo to use MongoDB Atlas Vector Store"
            raise ImportError(msg) from e

        try:
            mongo_client: MongoClient = MongoClient(self.mongodb_atlas_cluster_uri)
            collection = mongo_client[self.db_name][self.collection_name]
        except Exception as e:
            msg = f"Failed to connect to MongoDB Atlas: {e}"
            raise ValueError(msg) from e

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            return MongoDBAtlasVectorSearch.from_documents(
                documents=documents, embedding=self.embedding, collection=collection, index_name=self.index_name
            )
        return MongoDBAtlasVectorSearch(
            embedding=self.embedding,
            collection=collection,
            index_name=self.index_name,
        )

    def search_documents(self) -> list[Data]:
        from bson.objectid import ObjectId

        vector_store = self.build_vector_store()

        if self.search_query and isinstance(self.search_query, str):
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )
            for doc in docs:
                doc.metadata = {
                    key: str(value) if isinstance(value, ObjectId) else value for key, value in doc.metadata.items()
                }

            data = docs_to_data(docs)
            self.status = data
            return data
        return []
