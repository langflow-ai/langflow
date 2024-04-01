from typing import Optional

from langchain.chains import RetrievalQAWithSourcesChain
from langchain_core.documents import Document

from langflow.field_typing import BaseLanguageModel, BaseMemory, BaseRetriever, Text
from langflow.interface.custom.custom_component import CustomComponent


class RetrievalQAWithSourcesChainComponent(CustomComponent):
    display_name = "RetrievalQAWithSourcesChain"
    description = "Question-answering with sources over an index."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "chain_type": {
                "display_name": "Chain Type",
                "options": ["Stuff", "Map Reduce", "Refine", "Map Rerank"],
                "info": "The type of chain to use to combined Documents.",
            },
            "memory": {"display_name": "Memory"},
            "return_source_documents": {"display_name": "Return Source Documents"},
            "retriever": {"display_name": "Retriever"},
            "input_value": {
                "display_name": "Input Value",
                "info": "The input value to pass to the chain.",
            },
        }

    def build(
        self,
        input_value: Text,
        retriever: BaseRetriever,
        llm: BaseLanguageModel,
        chain_type: str,
        memory: Optional[BaseMemory] = None,
        return_source_documents: Optional[bool] = True,
    ) -> Text:
        chain_type = chain_type.lower().replace(" ", "_")
        runnable = RetrievalQAWithSourcesChain.from_chain_type(
            llm=llm,
            chain_type=chain_type,
            memory=memory,
            return_source_documents=return_source_documents,
            retriever=retriever,
        )
        if isinstance(input_value, Document):
            input_value = input_value.page_content
        self.status = runnable
        input_key = runnable.input_keys[0]
        result = runnable.invoke({input_key: input_value})
        result = result.content if hasattr(result, "content") else result
        # Result is a dict with keys "query",  "result" and "source_documents"
        # for now we just return the result
        records = self.to_records(result.get("source_documents"))
        references_str = ""
        if return_source_documents:
            references_str = self.create_references_from_records(records)
        result_str = Text(result.get("answer", ""))
        final_result = "\n".join([result_str, references_str])
        self.status = final_result
        return final_result
