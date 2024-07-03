# from langflow.field_typing import Data
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_core.vectorstores import VectorStore

from langflow.custom import CustomComponent
from langflow.field_typing import LanguageModel, Text
from langflow.schema import Data
from langflow.schema.message import Message


class SelfQueryRetrieverComponent(CustomComponent):
    display_name: str = "Self Query Retriever"
    description: str = "Retriever that uses a vector store and an LLM to generate the vector store queries."
    name = "SelfQueryRetriever"
    icon = "LangChain"

    def build_config(self):
        return {
            "query": {
                "display_name": "Query",
                "input_types": ["Message", "Text"],
                "info": "Query to be passed as input.",
            },
            "vectorstore": {
                "display_name": "Vector Store",
                "info": "Vector Store to be passed as input.",
            },
            "attribute_infos": {
                "display_name": "Metadata Field Info",
                "info": "Metadata Field Info to be passed as input.",
            },
            "document_content_description": {
                "display_name": "Document Content Description",
                "info": "Document Content Description to be passed as input.",
            },
            "llm": {
                "display_name": "LLM",
                "info": "LLM to be passed as input.",
            },
        }

    def build(
        self,
        query: Message,
        vectorstore: VectorStore,
        attribute_infos: list[Data],
        document_content_description: Text,
        llm: LanguageModel,
    ) -> Data:
        metadata_field_infos = [AttributeInfo(**value.data) for value in attribute_infos]
        self_query_retriever = SelfQueryRetriever.from_llm(
            llm=llm,
            vectorstore=vectorstore,
            document_contents=document_content_description,
            metadata_field_info=metadata_field_infos,
            enable_limit=True,
        )

        if isinstance(query, Message):
            input_text = query.text
        elif isinstance(query, str):
            input_text = query

        if not isinstance(query, str):
            raise ValueError(f"Query type {type(query)} not supported.")
        documents = self_query_retriever.invoke(input=input_text)
        data = [Data.from_document(document) for document in documents]
        self.status = data
        return data
