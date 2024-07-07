from typing import List

import weaviate  # type: ignore
from langchain_community.vectorstores import Weaviate

from langflow.base.vectorstores.model import LCVectorStoreComponent
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, HandleInput, IntInput, StrInput, SecretStrInput, DataInput, MultilineInput
from langflow.schema import Data


class WeaviateVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Weaviate"
    description = "Weaviate Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/weaviate"
    name = "Weaviate"
    icon = "Weaviate"

    inputs = [
        StrInput(name="url", display_name="Weaviate URL", value="http://localhost:8080", required=True),
        SecretStrInput(name="api_key", display_name="API Key", required=False),
        StrInput(name="index_name", display_name="Index Name", required=True),
        StrInput(name="text_key", display_name="Text Key", value="text", advanced=True),
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
        BoolInput(name="search_by_text", display_name="Search By Text", advanced=True),
    ]

    def build_vector_store(self) -> Weaviate:
        return self._build_weaviate()

    def _build_weaviate(self) -> Weaviate:
        if self.api_key:
            auth_config = weaviate.AuthApiKey(api_key=self.api_key)
            client = weaviate.Client(url=self.url, auth_client_secret=auth_config)
        else:
            client = weaviate.Client(url=self.url)

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents and self.embedding:
            return Weaviate.from_documents(
                client=client,
                index_name=self.index_name,
                documents=documents,
                embedding=self.embedding,
                by_text=self.search_by_text,
            )

        return Weaviate(
            client=client,
            index_name=self.index_name,
            text_key=self.text_key,
            embedding=self.embedding,
            by_text=self.search_by_text,
        )

    def search_documents(self) -> List[Data]:
        vector_store = self._build_weaviate()

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
