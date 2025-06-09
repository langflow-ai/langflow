from langchain_core.vectorstores import VectorStoreRetriever

from langflow.custom.custom_component.component import Component
from langflow.field_typing import VectorStore
from langflow.inputs.inputs import HandleInput


class VectoStoreRetrieverComponent(Component):
    display_name = "VectorStore Retriever"
    description = "A vector store retriever"
    name = "VectorStoreRetriever"
    icon = "LangChain"

    inputs = [
        HandleInput(
            name="vectorstore",
            display_name="Vector Store",
            input_types=["VectorStore"],
            required=True,
        ),
    ]

    def build(self, vectorstore: VectorStore) -> VectorStoreRetriever:
        return vectorstore.as_retriever()
