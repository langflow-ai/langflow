from langchain.agents import AgentExecutor, create_vectorstore_router_agent
from langchain.agents.agent_toolkits.vectorstore.toolkit import VectorStoreRouterToolkit

from langflow.base.agents.agent import LCAgentComponent
from langflow.inputs.inputs import HandleInput


class VectorStoreRouterAgentComponent(LCAgentComponent):
    display_name = "VectorStoreRouterAgent"
    description = "Construct an agent from a Vector Store Router."
    name = "VectorStoreRouterAgent"
    legacy: bool = True

    inputs = [
        *LCAgentComponent._base_inputs,
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True,
        ),
        HandleInput(
            name="vectorstores",
            display_name="Vector Stores",
            input_types=["VectorStoreInfo"],
            is_list=True,
            required=True,
        ),
    ]

    def build_agent(self) -> AgentExecutor:
        toolkit = VectorStoreRouterToolkit(vectorstores=self.vectorstores, llm=self.llm)
        return create_vectorstore_router_agent(llm=self.llm, toolkit=toolkit, **self.get_agent_kwargs())
