from typing import List

from langchain_community.vectorstores import MongoDBAtlasVectorSearch

from langflow.base.vectorstores.model import LCVectorStoreComponent
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, HandleInput, IntInput, StrInput, SecretStrInput, DataInput, MultilineInput
from langflow.schema import Data


class MongoVectorStoreComponent(LCVectorStoreComponent):
    display_name = "MongoDB Atlas"
    description = "MongoDB Atlas Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/mongodb_atlas"
    icon = "MongoDB"

    inputs = [
        SecretStrInput(name="mongodb_atlas_cluster_uri", display_name="MongoDB Atlas Cluster URI", required=True),
        StrInput(name="db_name", display_name="Database Name", required=True),
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        StrInput(name="index_name", display_name="Index Name", required=True),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        DataInput(
            name="vector_store_inputs",
            display_name="Vector Store Inputs",
            is_list=True,
        ),
        BoolInput(
            name="add_to_vector_store",
            display_name="Add to Vector Store",
            info="If true, the Vector Store Inputs will be added to the Vector Store.",
        ),
        MultilineInput(name="search_input", display_name="Search Input"),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
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
                    index_name=self.index_name
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
        from typing import Union
        from bson import ObjectId
        from langchain.schema import Document
        import json
        vector_store = self._build_mongodb_atlas()
        class JSONEncoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, Union[ObjectId, Document]):
                    return str(o)
                return super(JSONEncoder, self).default(o)
        if self.search_input and isinstance(self.search_input, str):
            docs = vector_store.similarity_search(
                query=self.search_input,
                k=self.number_of_results,
            )
            for index in range(len(docs)):
                docs[index].metadata = {key:str(docs[index].metadata[key]) if isinstance(docs[index].metadata[key], ObjectId) else docs[index].metadata[key] for key in docs[index].metadata}
            data = docs_to_data(docs)
            self.status = data
            return data
        else:
            return []
