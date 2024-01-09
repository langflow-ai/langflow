
from langflow import CustomComponent
from langchain.toolkits import VectorStoreToolkit
from langflow.field_typing import (
    VectorStore,
    Tool,
)

class VectorStoreToolkitComponent(CustomComponent):
    display_name = "VectorStoreToolkit"
    description = "Toolkit for interacting with a Vector Store."

    def build_config(self):
        return {
            "vectorstore_info": {"display_name": "Vector Store Info"},
        }

    def build(
        self,
        vectorstore_info: VectorStore,
    ) -> Tool:
        return VectorStoreToolkit(vectorstore_info=vectorstore_info)
