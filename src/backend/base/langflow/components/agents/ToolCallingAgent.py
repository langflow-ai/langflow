from typing import List, Optional

from langchain.agents.tool_calling_agent.base import create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate

from langflow.base.agents.agent import LCAgentComponent
from langflow.field_typing import BaseLanguageModel, Text, Tool
from langflow.schema import Record


class ToolCallingAgentComponent(LCAgentComponent):
    display_name: str = "Tool Calling Agent"
    description: str = "Agent that uses tools. Only models that are compatible with function calling are supported."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "tools": {"display_name": "Tools"},
            "user_prompt": {
                "display_name": "Prompt",
                "multiline": True,
                "info": "This prompt must contain 'input' key.",
            },
            "handle_parsing_errors": {
                "display_name": "Handle Parsing Errors",
                "info": "If True, the agent will handle parsing errors. If False, the agent will raise an error.",
                "advanced": True,
            },
            "memory": {
                "display_name": "Memory",
                "info": "Memory to use for the agent.",
            },
            "input_value": {
                "display_name": "Inputs",
                "info": "Input text to pass to the agent.",
            },
        }

    async def build(
        self,
        input_value: str,
        llm: BaseLanguageModel,
        tools: List[Tool],
        user_prompt: str = "{input}",
        message_history: Optional[List[Record]] = None,
        system_message: str = "You are a helpful assistant",
        handle_parsing_errors: bool = True,
    ) -> Text:
        if "input" not in user_prompt:
            raise ValueError("Prompt must contain 'input' key.")
        messages = [
            ("system", system_message),
            (
                "placeholder",
                "{chat_history}",
            ),
            ("human", user_prompt),
            ("placeholder", "{agent_scratchpad}"),
        ]
        prompt = ChatPromptTemplate.from_messages(messages)
        agent = create_tool_calling_agent(llm, tools, prompt)
        result = await self.run_agent(agent, input_value, tools, message_history, handle_parsing_errors)
        self.status = result
        return result
