from langflow import CustomComponent
from langchain.agents.agent_toolkits.vectorstore.toolkit import VectorStoreToolkit
from langchain.agents.agent_toolkits.vectorstore.toolkit import VectorStoreInfo
from langflow.field_typing import (
    BaseLanguageModel,
)
from langflow.field_typing import (
    Tool,
)
from typing import Union


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
