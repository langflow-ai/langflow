from typing import List

from langchain_community.vectorstores.redis import Redis

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import HandleInput, IntInput, StrInput, SecretStrInput, DataInput, MultilineInput
from langflow.schema import Data
from langchain.text_splitter import CharacterTextSplitter


class RedisVectorStoreComponent(LCVectorStoreComponent):
    """
    A custom component for implementing a Vector Store using Redis.
    """

    display_name: str = "Redis"
    description: str = "Implementation of Vector Store using Redis"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/redis"
    name = "Redis"

    inputs = [
        SecretStrInput(name="redis_server_url", display_name="Redis Server Connection String", required=True),
        StrInput(
            name="redis_index_name",
            display_name="Redis Index",
        ),
        StrInput(name="code", display_name="Code", advanced=True),
        StrInput(
            name="schema",
            display_name="Schema",
        ),
        MultilineInput(name="search_query", display_name="Search Query"),
        DataInput(
            name="ingest_data",
            display_name="Ingest Data",
            is_list=True,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> Redis:
        documents = []

        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        with open("docuemnts.txt", "w") as f:
            f.write(str(documents))

        if not documents:
            if self.schema is None:
                raise ValueError("If no documents are provided, a schema must be provided.")
            redis_vs = Redis.from_existing_index(
                embedding=self.embedding,
                index_name=self.redis_index_name,
                schema=self.schema,
                key_prefix=None,
                redis_url=self.redis_server_url,
            )
        else:
            text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
            docs = text_splitter.split_documents(documents)
            redis_vs = Redis.from_documents(
                documents=docs,
                embedding=self.embedding,
                redis_url=self.redis_server_url,
                index_name=self.redis_index_name,
            )
        return redis_vs

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
