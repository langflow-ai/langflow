
from langflow import CustomComponent
from langchain.chains import RetrievalQAWithSourcesChain
from typing import Optional
from langflow.field_typing import (
    BaseMemory,
    BaseRetriever,
    Chain,
)

class RetrievalQAWithSourcesChainComponent(CustomComponent):
    display_name = "RetrievalQAWithSourcesChain"
    description = "Question-answering with sources over an index."

    def build_config(self):
        return {
            "combine_documents_chain": {"display_name": "Combine Documents Chain"},
            "retriever": {"display_name": "Retriever"},
            "memory": {"display_name": "Memory", "optional": True},
            "return_source_documents": {"display_name": "Return Source Documents", "default": True, "advanced": True},
        }

    def build(
        self,
        combine_documents_chain: Chain,
        retriever: BaseRetriever,
        memory: Optional[BaseMemory] = None,
        return_source_documents: Optional[bool] = True,
    ) -> RetrievalQAWithSourcesChain:
        return RetrievalQAWithSourcesChain(
            combine_documents_chain=combine_documents_chain,
            retriever=retriever,
            memory=memory,
            return_source_documents=return_source_documents
        )
