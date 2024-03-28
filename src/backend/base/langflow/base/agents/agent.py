from typing import List, Optional, Union, cast

from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain_core.runnables import Runnable

from langflow.custom import CustomComponent
from langflow.field_typing import BaseMemory, Text, Tool


class LCAgentComponent(CustomComponent):
    def build_config(self):
        return {
            "lc": {
                "display_name": "LangChain",
                "info": "The LangChain to interact with.",
            },
            "handle_parsing_errors": {
                "display_name": "Handle Parsing Errors",
                "info": "If True, the agent will handle parsing errors. If False, the agent will raise an error.",
                "advanced": True,
            },
            "output_key": {
                "display_name": "Output Key",
                "info": "The key to use to get the output from the agent.",
                "advanced": True,
            },
            "memory": {
                "display_name": "Memory",
                "info": "Memory to use for the agent.",
            },
            "tools": {
                "display_name": "Tools",
                "info": "Tools the agent can use.",
            },
            "input_value": {
                "display_name": "Input",
                "info": "Input text to pass to the agent.",
            },
        }

    async def run_agent(
        self,
        agent: Union[Runnable, BaseSingleActionAgent, BaseMultiActionAgent, AgentExecutor],
        inputs: str,
        input_variables: list[str],
        tools: List[Tool],
        memory: Optional[BaseMemory] = None,
        handle_parsing_errors: bool = True,
        output_key: str = "output",
    ) -> Text:
        if isinstance(agent, AgentExecutor):
            runnable = agent
        else:
            runnable = AgentExecutor.from_agent_and_tools(
                agent=agent,  # type: ignore
                tools=tools,
                verbose=True,
                memory=memory,
                handle_parsing_errors=handle_parsing_errors,
            )
        input_dict = {"input": inputs}
        for var in input_variables:
            if var not in ["agent_scratchpad", "input"]:
                input_dict[var] = ""
        result = await runnable.ainvoke(input_dict)
        self.status = result
        if output_key in result:
            return cast(str, result.get(output_key))
        elif "output" not in result:
            if output_key != "output":
                raise ValueError(f"Output key not found in result. Tried '{output_key}' and 'output'.")
            else:
                raise ValueError("Output key not found in result. Tried 'output'.")

        return cast(str, result.get("output"))
