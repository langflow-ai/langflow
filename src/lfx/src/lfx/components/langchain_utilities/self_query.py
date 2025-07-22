from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import HandleInput, MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data
from lfx.schema.message import Message


class SelfQueryRetrieverComponent(Component):
    display_name = "Self Query Retriever"
    description = "Retriever that uses a vector store and an LLM to generate the vector store queries."
    name = "SelfQueryRetriever"
    icon = "LangChain"
    legacy: bool = True

    inputs = [
        HandleInput(
            name="query",
            display_name="Query",
            info="Query to be passed as input.",
            input_types=["Message"],
        ),
        HandleInput(
            name="vectorstore",
            display_name="Vector Store",
            info="Vector Store to be passed as input.",
            input_types=["VectorStore"],
        ),
        HandleInput(
            name="attribute_infos",
            display_name="Metadata Field Info",
            info="Metadata Field Info to be passed as input.",
            input_types=["Data"],
            is_list=True,
        ),
        MessageTextInput(
            name="document_content_description",
            display_name="Document Content Description",
            info="Document Content Description to be passed as input.",
        ),
        HandleInput(
            name="llm",
            display_name="LLM",
            info="LLM to be passed as input.",
            input_types=["LanguageModel"],
        ),
    ]

    outputs = [
        Output(
            display_name="Retrieved Documents",
            name="documents",
            method="retrieve_documents",
        ),
    ]

    def retrieve_documents(self) -> list[Data]:
        metadata_field_infos = [AttributeInfo(**value.data) for value in self.attribute_infos]
        self_query_retriever = SelfQueryRetriever.from_llm(
            llm=self.llm,
            vectorstore=self.vectorstore,
            document_contents=self.document_content_description,
            metadata_field_info=metadata_field_infos,
            enable_limit=True,
        )

        if isinstance(self.query, Message):
            input_text = self.query.text
        elif isinstance(self.query, str):
            input_text = self.query
        else:
            msg = f"Query type {type(self.query)} not supported."
            raise TypeError(msg)

        documents = self_query_retriever.invoke(input=input_text, config={"callbacks": self.get_langchain_callbacks()})
        data = [Data.from_document(document) for document in documents]
        self.status = data
        return data
