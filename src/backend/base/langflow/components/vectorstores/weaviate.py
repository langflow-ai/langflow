import weaviate
from langchain_community.vectorstores import Weaviate

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, HandleInput, IntInput, SecretStrInput, StrInput
from langflow.schema import Data


class WeaviateVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Weaviate"
    description = "Weaviate Vector Store with search capabilities"
    name = "Weaviate"
    icon = "Weaviate"

    inputs = [
        StrInput(name="url", display_name="Weaviate URL", value="http://localhost:8080", required=True),
        SecretStrInput(name="api_key", display_name="API Key", required=False),
        StrInput(
            name="index_name",
            display_name="Index Name",
            required=True,
            info="Requires capitalized index name.",
        ),
        StrInput(name="text_key", display_name="Text Key", value="text", advanced=True),
        *LCVectorStoreComponent.inputs,
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

    @check_cached_vector_store
    def build_vector_store(self) -> Weaviate:
        if self.api_key:
            auth_config = weaviate.AuthApiKey(api_key=self.api_key)
            client = weaviate.Client(url=self.url, auth_client_secret=auth_config)
        else:
            client = weaviate.Client(url=self.url)

        if self.index_name != self.index_name.capitalize():
            msg = f"Weaviate requires the index name to be capitalized. Use: {self.index_name.capitalize()}"
            raise ValueError(msg)

        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

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
