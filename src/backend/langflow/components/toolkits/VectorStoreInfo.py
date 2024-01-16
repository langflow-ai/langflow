
from langflow import CustomComponent
from langchain.vectorstores import VectorStore
from typing import Union, Callable
from langchain.agents.agent_toolkits.vectorstore.toolkit import VectorStoreInfo

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
    ) -> Union[VectorStoreInfo, Callable]:
        return VectorStoreInfo(vectorstore=vectorstore, description=description, name=name)
