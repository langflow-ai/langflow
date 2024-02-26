from typing import Optional

from langchain.chains import RetrievalQAWithSourcesChain
from langchain.chains.combine_documents.base import BaseCombineDocumentsChain
from langchain_core.documents import Document

from langflow import CustomComponent
from langflow.field_typing import BaseLanguageModel, BaseMemory, BaseRetriever, Text


class RetrievalQAWithSourcesChainComponent(CustomComponent):
    display_name = "RetrievalQAWithSourcesChain"
    description = "Question-answering with sources over an index."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "chain_type": {
                "display_name": "Chain Type",
                "options": ["stuff", "map_reduce", "map_rerank", "refine"],
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
    ) -> Text:
        runnable = RetrievalQAWithSourcesChain.from_chain_type(
            llm=llm,
            chain_type=chain_type,
            combine_documents_chain=combine_documents_chain,
            memory=memory,
            return_source_documents=return_source_documents,
            retriever=retriever,
        )
        if isinstance(inputs, Document):
            inputs = inputs.page_content
        self.status = runnable
        input_key = runnable.input_keys[0]
        result = runnable.invoke({input_key: inputs})
        result = result.content if hasattr(result, "content") else result
        # Result is a dict with keys "query",  "result" and "source_documents"
        # for now we just return the result
        records = self.to_records(result.get("source_documents"))
        references_str = ""
        if return_source_documents:
            references_str = self.create_references_from_records(records)
        result_str = result.get("result")
        final_result = "\n".join([result_str, references_str])
        self.status = final_result
        return final_result
