from typing import List, Optional, Union, cast
import re

from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain_core.messages import BaseMessage, AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain.callbacks.base import BaseCallbackHandler

from langflow.base.agents.utils import get_agents_list, records_to_messages
from langflow.custom import CustomComponent
from langflow.field_typing import Text, Tool
from langflow.schema import Record
from langflow.schema.message import Message

class LCAgentComponent(CustomComponent):
    def get_agents_list(self):
        return get_agents_list()

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
        tools: List[Tool],
        message_history: Optional[List[Record]] = None,
        handle_parsing_errors: bool = True,
        output_key: str = "output",
        lc_callback: Optional[List[BaseCallbackHandler]] = None,
    ) -> Text:
        if isinstance(agent, AgentExecutor):
            runnable = agent
        else:
            runnable = AgentExecutor.from_agent_and_tools(
                agent=agent,  # type: ignore
                tools=tools,
                verbose=True,
                handle_parsing_errors=handle_parsing_errors,
            )
        input_dict: dict[str, Union[str, List[dict]]] = {"input": inputs}

        if message_history:
            chat_history = []
            for record in message_history:
                message = record.to_lc_message()
                if isinstance(message, HumanMessage):
                    role = "user"
                elif isinstance(message, AIMessage):
                    role = "assistant"
                elif isinstance(message, SystemMessage):
                    role = "system"
                else:
                    role = "unknown"

                # Flatten the content if it is a list
                if isinstance(message.content, list):
                    content = ' '.join([item['text'] for item in message.content if 'text' in item])
                else:
                    content = message.content

                # Filter out serialized data-like entries using a regular expression pattern
                # This pattern looks for key=value pairs which are typical in serialized data
                if re.search(r'\w+=', content):
                    continue

                chat_history.append({
                    'role': role,
                    'content': content
                })

            input_dict["chat_history"] = chat_history

        # Pass the callback to the acall method
        result = await runnable.ainvoke(input_dict, config={"callbacks": lc_callback if lc_callback else []})

        self.status = result
        if output_key in result:
            return cast(str, result.get(output_key))
        elif "output" not in result:
            if output_key != "output":
                raise ValueError(f"Output key not found in result. Tried '{output_key}' and 'output'.")
            else:
                raise ValueError("Output key not found in result. Tried 'output'.")

        return cast(str, result.get("output"))

