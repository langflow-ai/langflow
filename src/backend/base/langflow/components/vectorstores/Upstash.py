from typing import List

from langchain_community.vectorstores import UpstashVectorStore

from langflow.base.vectorstores.model import LCVectorStoreComponent
from langflow.helpers.data import docs_to_data
from langflow.io import HandleInput, IntInput, StrInput, SecretStrInput, DataInput, MultilineInput
from langflow.schema import Data


class UpstashVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Upstash"
    description = "Upstash Vector Store with search capabilities"
    documentation = "https://python.langchain.com/v0.2/docs/integrations/vectorstores/upstash/"
    name = "Upstash"
    icon = "Upstash"

    inputs = [
        StrInput(name="index_url", display_name="Index URL", info="The URL of the Upstash index.", required=True),
        SecretStrInput(
            name="index_token", display_name="Index Token", info="The token for the Upstash index.", required=True
        ),
        StrInput(
            name="text_key",
            display_name="Text Key",
            info="The key in the record to use as text.",
            value="text",
            advanced=True,
        ),
        MultilineInput(name="search_query", display_name="Search Query"),
        DataInput(
            name="ingest_data",
            display_name="Ingest Data",
            is_list=True,
        ),
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"],
            info="To use Upstash's embeddings, don't provide an embedding.",
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    def build_vector_store(self) -> UpstashVectorStore:
        return self._build_upstash()

    def _build_upstash(self) -> UpstashVectorStore:
        use_upstash_embedding = self.embedding is None

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            if use_upstash_embedding:
                upstash_vs = UpstashVectorStore(
                    embedding=use_upstash_embedding,
                    text_key=self.text_key,
                    index_url=self.index_url,
                    index_token=self.index_token,
                )
                upstash_vs.add_documents(documents)
            else:
                upstash_vs = UpstashVectorStore.from_documents(
                    documents=documents,
                    embedding=self.embedding,
                    text_key=self.text_key,
                    index_url=self.index_url,
                    index_token=self.index_token,
                )
        else:
            upstash_vs = UpstashVectorStore(
                embedding=self.embedding or use_upstash_embedding,
                text_key=self.text_key,
                index_url=self.index_url,
                index_token=self.index_token,
            )

        return upstash_vs

    def search_documents(self) -> List[Data]:
        vector_store = self._build_upstash()

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
