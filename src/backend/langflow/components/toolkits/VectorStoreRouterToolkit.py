
from langflow import CustomComponent
from typing import List
from langchain.vectorstores import VectorStore

class VectorStoreRouterToolkitComponent(CustomComponent):
    display_name = "VectorStoreRouterToolkit"
    description = "Toolkit for routing between Vector Stores."

    def build_config(self):
        return {
            "vectorstores": {"display_name": "Vector Stores"},
        }

    def build(
        self,
        vectorstores: List[VectorStore],
    ):
        # Assuming the class `VectorStoreRouterToolkit` exists within a module, but since there
        # is no further information provided about the module structure, I will assume it is
        # accessible from the current context. If it's in `langchain.vectorstores`, it should be
        # imported from there.
        return VectorStoreRouterToolkit(vectorstores=vectorstores)
