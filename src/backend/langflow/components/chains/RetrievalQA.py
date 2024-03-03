from typing import Optional

from langchain.chains.combine_documents.base import BaseCombineDocumentsChain
from langchain.chains.retrieval_qa.base import RetrievalQA
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
            "input_value": {
                "display_name": "Input",
                "input_types": ["Text", "Document"],
            },
        }

    def build(
        self,
        combine_documents_chain: BaseCombineDocumentsChain,
        retriever: BaseRetriever,
        input_value: str = "",
        memory: Optional[BaseMemory] = None,
        input_key: str = "query",
        output_key: str = "result",
        return_source_documents: bool = True,
    ) -> Text:
        runnable = RetrievalQA(
            combine_documents_chain=combine_documents_chain,
            retriever=retriever,
            memory=memory,
            input_key=input_key,
            output_key=output_key,
            return_source_documents=return_source_documents,
        )
        if isinstance(input_value, Document):
            input_value = input_value.page_content
        self.status = runnable
        result = runnable.invoke({input_key: input_value})
        result = result.content if hasattr(result, "content") else result
        # Result is a dict with keys "query",  "result" and "source_documents"
        # for now we just return the result
        records = self.to_records(result.get("source_documents"))
        references_str = ""
        if return_source_documents:
            references_str = self.create_references_from_records(records)
        result_str = result.get("result", "")

        final_result = "\n".join([Text(result_str), references_str])
        self.status = final_result
        return final_result  # OK
