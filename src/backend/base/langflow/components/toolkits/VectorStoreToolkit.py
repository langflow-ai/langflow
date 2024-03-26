from typing import Union

from langchain.agents.agent_toolkits.vectorstore.toolkit import VectorStoreInfo, VectorStoreToolkit

from langflow.field_typing import BaseLanguageModel, Tool
from langflow.interface.custom.custom_component import CustomComponent


class VectorStoreToolkitComponent(CustomComponent):
    display_name = "VectorStoreToolkit"
    description = "Toolkit for interacting with a Vector Store."

    def build_config(self):
        return {
            "vectorstore_info": {"display_name": "Vector Store Info"},
            "llm": {"display_name": "LLM"},
        }

    def build(
        self,
        vectorstore_info: VectorStoreInfo,
        llm: BaseLanguageModel,
    ) -> Union[Tool, VectorStoreToolkit]:
        return VectorStoreToolkit(vectorstore_info=vectorstore_info, llm=llm)
