
from langflow import CustomComponent
from typing import List
from langchain.agents.agent_toolkits.vectorstore.toolkit import VectorStoreRouterToolkit
from langchain.agents.agent_toolkits.vectorstore.toolkit import VectorStoreInfo

class VectorStoreRouterToolkitComponent(CustomComponent):
    display_name = "VectorStoreRouterToolkit"
    description = "Toolkit for routing between Vector Stores."

    def build_config(self):
        return {
            "vectorstores": {"display_name": "Vector Stores"},
        }

    def build(
        self,
        vectorstores: List[VectorStoreInfo],
    ):
        # Assuming the class `VectorStoreRouterToolkit` exists within a module, but since there
        # is no further information provided about the module structure, I will assume it is
        # accessible from the current context. If it's in `langchain.vectorstores`, it should be
        # imported from there.
        return VectorStoreRouterToolkit(vectorstores=vectorstores)
