from typing import cast

from langchain.retrievers import ContextualCompressionRetriever
from langchain_cohere import CohereRerank

from langflow.base.vectorstores.model import (
    LCVectorStoreComponent,
    check_cached_vector_store,
)
from langflow.field_typing import Retriever, VectorStore
from langflow.io import (
    DropdownInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    SecretStrInput,
)
from langflow.schema import Data
from langflow.template.field.base import Output


class CohereRerankComponent(LCVectorStoreComponent):
    display_name = "Cohere Rerank"
    description = "Rerank documents using the Cohere API and a retriever."
    name = "CohereRerank"
    icon = "Cohere"
    legacy: bool = True

    inputs = [
        MultilineInput(
            name="search_query",
            display_name="Search Query",
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            options=[
                "rerank-english-v3.0",
                "rerank-multilingual-v3.0",
                "rerank-english-v2.0",
                "rerank-multilingual-v2.0",
            ],
            value="rerank-english-v3.0",
        ),
        SecretStrInput(name="api_key", display_name="API Key"),
        IntInput(name="top_n", display_name="Top N", value=3),
        MessageTextInput(
            name="user_agent",
            display_name="User Agent",
            value="langflow",
            advanced=True,
        ),
        HandleInput(name="retriever", display_name="Retriever", input_types=["Retriever"]),
    ]

    outputs = [
        Output(
            display_name="Retriever",
            name="base_retriever",
            method="build_base_retriever",
        ),
        Output(
            display_name="Search Results",
            name="search_results",
            method="search_documents",
        ),
    ]

    def build_base_retriever(self) -> Retriever:  # type: ignore[type-var]
        cohere_reranker = CohereRerank(
            cohere_api_key=self.api_key,
            model=self.model,
            top_n=self.top_n,
            user_agent=self.user_agent,
        )
        retriever = ContextualCompressionRetriever(base_compressor=cohere_reranker, base_retriever=self.retriever)
        return cast(Retriever, retriever)

    async def search_documents(self) -> list[Data]:  # type: ignore[override]
        retriever = self.build_base_retriever()
        documents = await retriever.ainvoke(self.search_query, config={"callbacks": self.get_langchain_callbacks()})
        data = self.to_data(documents)
        self.status = data
        return data

    @check_cached_vector_store
    def build_vector_store(self) -> VectorStore:
        msg = "Cohere Rerank does not support vector stores."
        raise NotImplementedError(msg)
