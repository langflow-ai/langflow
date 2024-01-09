
from langflow import CustomComponent
from langchain.vectorstores import VectorStore
from typing import Union, Callable
from langflow.field_typing import Chain

class VectorStoreInfoComponent(CustomComponent):
    display_name = "VectorStoreInfo"
    description = "Information about a VectorStore"

    def build_config(self):
        return {
            "vectorstore": {"display_name": "VectorStore"},
            "description": {"display_name": "Description", "multiline": True},
            "name": {"display_name": "Name"},
        }

    def build(
        self,
        vectorstore: VectorStore,
        description: str,
        name: str,
    ) -> Union[Chain, Callable]:
        # Since the actual implementation of VectorStoreInfo is not provided, this is a placeholder
        # Replace VectorStoreInfo with the actual class that should be instantiated
        # This is a hypothetical class, actual implementation may vary
        class VectorStoreInfo:
            def __init__(self, vectorstore, description, name):
                self.vectorstore = vectorstore
                self.description = description
                self.name = name

        return VectorStoreInfo(vectorstore=vectorstore, description=description, name=name)
