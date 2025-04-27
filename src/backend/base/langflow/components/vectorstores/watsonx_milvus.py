from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    HandleInput,
    IntInput,
    SecretStrInput,
    StrInput,
)
from langflow.schema import Data


class WatsonxDataMilvusVectorStoreComponent(LCVectorStoreComponent):
    """Milvus vector store with search capabilities."""

    display_name: str = "IBM watsonx.data Milvus"
    description: str = "Milvus vector store deployed on watsonx.data"
    name = "Milvus on watsonx.data"
    icon = "WatsonxData"

    inputs = [
        StrInput(name="collection_name", display_name="Collection Name", value="langflow"),
        StrInput(
            name="uri",
            display_name="Connection URI",
            value="",
        ),
        StrInput(name="username", display_name="Username", value="ibmlhapikey", required=True),
        SecretStrInput(name="api_key", display_name="IBM Api Key", value="", required=True),
        StrInput(name="primary_field", display_name="Primary Field Name", value="pk"),
        StrInput(name="text_field", display_name="Text Field Name", value="text"),
        StrInput(name="vector_field", display_name="Vector Field Name", value="vector"),
        DropdownInput(
            name="consistency_level",
            display_name="Consistencey Level",
            options=["Bounded", "Session", "Strong", "Eventual"],
            value="Session",
            advanced=True,
        ),
        DictInput(name="index_params", display_name="Index Parameters", advanced=True),
        DictInput(name="search_params", display_name="Search Parameters", advanced=True),
        BoolInput(name="drop_old", display_name="Drop Old Collection", value=False, advanced=True),
        FloatInput(name="timeout", display_name="Timeout", advanced=True),
        *LCVectorStoreComponent.inputs,
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
    def build_vector_store(self):
        try:
            from langchain_milvus.vectorstores import Milvus as LangchainMilvus
        except ImportError as e:
            msg = "Could not import Milvus integration package. Please install it with `pip install langchain-milvus`."
            raise ImportError(msg) from e

        connection_args = {"uri": self.uri, "password": self.api_key, "user": self.username, "secure": True}
        milvus_store = LangchainMilvus(
            embedding_function=self.embedding,
            collection_name=self.collection_name,
            connection_args=connection_args,
            consistency_level=self.consistency_level,
            index_params=self.index_params,
            search_params=self.search_params,
            drop_old=self.drop_old,
            auto_id=True,
            primary_field=self.primary_field,
            text_field=self.text_field,
            vector_field=self.vector_field,
            timeout=self.timeout,
        )

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            milvus_store.add_documents(documents)

        return milvus_store

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
