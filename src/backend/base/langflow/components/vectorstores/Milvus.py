from typing import List

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import (
    DataInput,
    StrInput,
    IntInput,
    FloatInput,
    BoolInput,
    DictInput,
    MultilineInput,
    DropdownInput,
    SecretStrInput,
    HandleInput,
)
from langflow.schema import Data


class MilvusVectorStoreComponent(LCVectorStoreComponent):
    """Milvus vector store with search capabilities"""

    display_name: str = "Milvus"
    description: str = "Milvus vector store with search capabilities"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/milvus"
    name = "Milvus"
    icon = "Milvus"

    inputs = [
        StrInput(name="collection_name", display_name="Collection Name", value="langflow"),
        StrInput(name="collection_description", display_name="Collection Description", value=""),
        StrInput(
            name="uri",
            display_name="Connection URI",
            value="http://localhost:19530",
        ),
        SecretStrInput(
            name="password",
            display_name="Connection Password",
            value="",
            info="Ignore this field if no password is required to make connection.",
        ),
        DictInput(name="connection_args", display_name="Other Connection Arguments", advanced=True),
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
    def build_vector_store(self):
        try:
            from langchain_milvus.vectorstores import Milvus as LangchainMilvus
        except ImportError:
            raise ImportError(
                "Could not import Milvus integration package. " "Please install it with `pip install langchain-milvus`."
            )
        self.connection_args.update(uri=self.uri, token=self.password)
        milvus_store = LangchainMilvus(
            embedding_function=self.embedding,
            collection_name=self.collection_name,
            collection_description=self.collection_description,
            connection_args=self.connection_args,
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

    def search_documents(self) -> List[Data]:
        vector_store = self.build_vector_store()

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
