# from langflow.field_typing import Data
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_core.vectorstores import VectorStore

from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel
from langflow.schema import Record
from langflow.schema.message import Message


class SelfQueryRetrieverComponent(CustomComponent):
    display_name: str = "Self Query Retriever"
    description: str = "Retriever that uses a vector store and an LLM to generate the vector store queries."
    icon = "LangChain"

    def build(
        self,
        query: Message,
        vectorstore: VectorStore,
        metadata_field_info: list[AttributeInfo],
        document_content_description: str,
        llm: BaseLanguageModel,
    ) -> Record:
        metadata_field_info = [i[0] for i in metadata_field_info]

        self_query_retriever = SelfQueryRetriever.from_llm(
            llm,
            vectorstore,
            document_content_description,
            metadata_field_info,
            enable_limit=True,
        )

        input_text = query.text
        documents = self_query_retriever.invoke(input=input_text)
        records = [Record.from_document(document) for document in documents]
        self.status = records
        return records
