
from langflow import CustomComponent
from langchain.chains import BaseRetrievalQA
from typing import Optional, Union, Callable
from langflow.field_typing import (
    BaseCombineDocumentsChain,
    BaseMemory,
    BaseRetriever,
)

class RetrievalQAComponent(CustomComponent):
    display_name = "RetrievalQA"
    description = "Chain for question-answering against an index."

    def build_config(self):
        return {
            "combine_documents_chain": {"display_name": "Combine Documents Chain"},
            "retriever": {"display_name": "Retriever"},
            "memory": {"display_name": "Memory", "required": False},
            "input_key": {"display_name": "Input Key"},
            "output_key": {"display_name": "Output Key"},
            "return_source_documents": {"display_name": "Return Source Documents"},
        }

    def build(
        self,
        combine_documents_chain: BaseCombineDocumentsChain,
        retriever: BaseRetriever,
        memory: Optional[BaseMemory] = None,
        input_key: str = "query",
        output_key: str = "result",
        return_source_documents: bool = True,
    ) -> Union[BaseRetrievalQA, Callable]:
        return BaseRetrievalQA(
            combine_documents_chain=combine_documents_chain,
            retriever=retriever,
            memory=memory,
            input_key=input_key,
            output_key=output_key,
            return_source_documents=return_source_documents,
        )
