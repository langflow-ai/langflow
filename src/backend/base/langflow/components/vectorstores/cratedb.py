import typing as t

from langchain_cratedb import CrateDBVectorStore

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers import docs_to_data
from langflow.io import HandleInput, IntInput, SecretStrInput, StrInput
from langflow.schema import Data


class CrateDBVectorStoreComponent(LCVectorStoreComponent):
    display_name = "CrateDBVector"
    description = "CrateDB Vector Store with search capabilities"
    name = "CrateDB"
    icon = "CrateDB"

    inputs = [
        SecretStrInput(name="server_url", display_name="CrateDB SQLAlchemy URL", required=True),
        StrInput(name="collection_name", display_name="Table", required=True),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"], required=True),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> CrateDBVectorStore:
        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        connection_string = self.server_url or "crate://"

        if documents:
            store = CrateDBVectorStore.from_documents(
                embedding=self.embedding,
                documents=documents,
                collection_name=self.collection_name,
                connection=connection_string,
            )
        else:
            store = CrateDBVectorStore.from_existing_index(
                embedding=self.embedding,
                collection_name=self.collection_name,
                connection=connection_string,
            )

        return store

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )

            data = docs_to_data(docs)
            self.status = data
            return data
        return []


def cratedb_collection_to_data(embedding_documents: list[t.Any]):
    """Converts a collection of CrateDB vectors into a list of data.

    Args:
        embedding_documents (dict): A list of EmbeddingStore instances.

    Returns:
        list: A list of data, where each record represents a document in the collection.
    """
    data = []
    for doc in embedding_documents:
        data_dict = {
            "id": doc.id,
            "text": doc.document,
        }
        data_dict.update(doc.cmetadata)
        data.append(Data(**data_dict))
    return data
