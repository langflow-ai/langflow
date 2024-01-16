
from langflow import CustomComponent
from langchain.chains import RetrievalQAWithSourcesChain
from langchain.chains.combine_documents.base import BaseCombineDocumentsChain
from typing import Optional
from langflow.field_typing import (
    BaseMemory,
    BaseRetriever,
    BaseLanguageModel
)

class RetrievalQAWithSourcesChainComponent(CustomComponent):
    display_name = "RetrievalQAWithSourcesChain"
    description = "Question-answering with sources over an index."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "chain_type": {
                "display_name": "Chain Type",
                "options": ['stuff', 'map_reduce', 'map_rerank', 'refine'],
            },
            "memory": {"display_name": "Memory"},
            "return_source_documents": {"display_name": "Return Source Documents"},

        }


    def build(
        self,
        retriever: BaseRetriever,
        llm: BaseLanguageModel,
        combine_documents_chain: BaseCombineDocumentsChain,
        chain_type: str,
        memory: Optional[BaseMemory] = None,
        return_source_documents: Optional[bool] = True,
    ) -> RetrievalQAWithSourcesChain:
        return RetrievalQAWithSourcesChain(combine_documents_chain=combine_documents_chain,memory=memory,return_source_documents=return_source_documents,retriever=retriever).from_chain_type(llm=llm, chain_type=chain_type)