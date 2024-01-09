
from langflow import CustomComponent
from langchain.agents import AgentExecutor
from typing import Union, Callable
from langflow.field_typing import BaseLanguageModel, VectorStore

class VectorStoreAgentComponent(CustomComponent):
    display_name = "VectorStoreAgent"
    description = "Construct an agent from a Vector Store."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "vectorstoreinfo": {"display_name": "Vector Store Info"},
        }

    def build(
        self,
        llm: BaseLanguageModel,
        vectorstoreinfo: VectorStore,
    ) -> Union[AgentExecutor, Callable]:
        return AgentExecutor(llm=llm, vectorstore=vectorstoreinfo)
