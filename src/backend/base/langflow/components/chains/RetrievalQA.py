from typing import Optional

from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain_core.documents import Document

from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel, BaseMemory, BaseRetriever, Text
from langflow.schema import Record


class RetrievalQAComponent(CustomComponent):
    display_name = "Retrieval QA"
    description = "Chain for question-answering against an index."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "chain_type": {"display_name": "Chain Type", "options": ["Stuff", "Map Reduce", "Refine", "Map Rerank"]},
            "retriever": {"display_name": "Retriever"},
            "memory": {"display_name": "Memory", "required": False},
            "input_key": {"display_name": "Input Key", "advanced": True},
            "output_key": {"display_name": "Output Key", "advanced": True},
            "return_source_documents": {"display_name": "Return Source Documents"},
            "input_value": {
                "display_name": "Input",
                "input_types": ["Record", "Document"],
            },
        }

    def build(
        self,
        llm: BaseLanguageModel,
        chain_type: str,
        retriever: BaseRetriever,
        input_value: str = "",
        memory: Optional[BaseMemory] = None,
        input_key: str = "query",
        output_key: str = "result",
        return_source_documents: bool = True,
    ) -> Text:
        chain_type = chain_type.lower().replace(" ", "_")
        runnable = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type=chain_type,
            retriever=retriever,
            memory=memory,
            input_key=input_key,
            output_key=output_key,
            return_source_documents=return_source_documents,
        )
        if isinstance(input_value, Document):
            input_value = input_value.page_content
        if isinstance(input_value, Record):
            input_value = input_value.get_text()
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
