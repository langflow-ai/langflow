from typing import Callable, Union

from langchain.agents import AgentExecutor, create_vectorstore_agent
from langchain.agents.agent_toolkits.vectorstore.toolkit import VectorStoreToolkit

from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel


class VectorStoreAgentComponent(CustomComponent):
    display_name = "VectorStoreAgent"
    description = "Construct an agent from a Vector Store."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "vector_store_toolkit": {"display_name": "Vector Store Info"},
        }

    def build(
        self,
        llm: BaseLanguageModel,
        vector_store_toolkit: VectorStoreToolkit,
    ) -> Union[AgentExecutor, Callable]:
        return create_vectorstore_agent(llm=llm, toolkit=vector_store_toolkit)
