from typing import Callable, Optional, Union

from langchain.chains.combine_documents.base import BaseCombineDocumentsChain
from langchain.chains.retrieval_qa.base import BaseRetrievalQA, RetrievalQA
from langchain_core.documents import Document
from langflow import CustomComponent
from langflow.field_typing import BaseMemory, BaseRetriever, Text


class RetrievalQAComponent(CustomComponent):
    display_name = "Retrieval QA"
    description = "Chain for question-answering against an index."

    def build_config(self):
        return {
            "combine_documents_chain": {"display_name": "Combine Documents Chain"},
            "retriever": {"display_name": "Retriever"},
            "memory": {"display_name": "Memory", "required": False},
            "input_key": {"display_name": "Input Key", "advanced": True},
            "output_key": {"display_name": "Output Key", "advanced": True},
            "return_source_documents": {"display_name": "Return Source Documents"},
            "inputs": {"display_name": "Input", "input_types": ["Text", "Document"]},
        }

    def build(
        self,
        combine_documents_chain: BaseCombineDocumentsChain,
        retriever: BaseRetriever,
        inputs: str = "",
        memory: Optional[BaseMemory] = None,
        input_key: str = "query",
        output_key: str = "result",
        return_source_documents: bool = True,
    ) -> Union[BaseRetrievalQA, Callable, Text]:
        runnable = RetrievalQA(
            combine_documents_chain=combine_documents_chain,
            retriever=retriever,
            memory=memory,
            input_key=input_key,
            output_key=output_key,
            return_source_documents=return_source_documents,
        )
        if isinstance(inputs, Document):
            inputs = inputs.page_content
        self.status = runnable
        result = runnable.invoke({input_key: inputs})
        result = result.content if hasattr(result, "content") else result
        # Result is a dict with keys "query",  "result" and "source_documents"
        # for now we just return the result
        return result.get("result")
