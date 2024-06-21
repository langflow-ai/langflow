from typing import List, cast

from langchain.agents import AgentExecutor, BaseSingleActionAgent
from langchain.agents.tool_calling_agent.base import create_tool_calling_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from langflow.custom import Component
from langflow.io import BoolInput, HandleInput, Output, TextInput
from langflow.schema import Data
from langflow.schema.message import Message


class ToolCallingAgentComponent(Component):
    display_name: str = "Tool Calling Agent"
    description: str = "Agent that uses tools. Only models that are compatible with function calling are supported."
    icon = "Agent"

    inputs = [
        HandleInput(
            name="llm",
            display_name="LLM",
            input_types=["LanguageModel"],
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
        ),
        TextInput(
            name="user_prompt",
            display_name="Prompt",
            info="This prompt must contain 'input' key.",
            value="{input}",
        ),
        BoolInput(
            name="handle_parsing_errors",
            display_name="Handle Parsing Errors",
            info="If True, the agent will handle parsing errors. If False, the agent will raise an error.",
            advanced=True,
            value=True,
        ),
        HandleInput(
            name="memory",
            display_name="Memory",
            input_types=["Data"],
            info="Memory to use for the agent.",
        ),
        TextInput(
            name="input_value",
            display_name="Inputs",
            info="Input text to pass to the agent.",
        ),
    ]

    outputs = [
        Output(display_name="Text", name="text_output", method="run_agent"),
    ]

    async def run_agent(self) -> Message:
        if "input" not in self.user_prompt:
            raise ValueError("Prompt must contain 'input' key.")
        messages = [
            ("system", "You are a helpful assistant"),
            (
                "placeholder",
                "{chat_history}",
            ),
            ("human", self.user_prompt),
            ("placeholder", "{agent_scratchpad}"),
        ]
        prompt = ChatPromptTemplate.from_messages(messages)
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)

        runnable = AgentExecutor.from_agent_and_tools(
            agent=cast(BaseSingleActionAgent, agent),
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=self.handle_parsing_errors,
        )
        input_dict: dict[str, str | list[BaseMessage]] = {"input": self.input_value}
        if hasattr(self, "memory") and self.memory:
            input_dict["chat_history"] = self.convert_chat_history(self.memory)
        result = await runnable.ainvoke(input_dict)
        self.status = result

        if "output" not in result:
            raise ValueError("Output key not found in result. Tried 'output'.")

        result_string = result["output"]

        return Message(text=result_string)

    def convert_chat_history(self, chat_history: List[Message | Data]) -> List[BaseMessage]:
        messages = []
        for item in chat_history:
            if isinstance(item, (Message, Data)):
                messages.append(item.to_lc_message())
            elif isinstance(item, str):
                messages.append(HumanMessage(content=item))
            elif isinstance(item, dict) and "sender" in item and "text" in item:
                messages.append(HumanMessage(content=item["text"], sender=item["sender"]))
            else:
                raise ValueError(f"Invalid item ({type(item)}) in chat history: {item}")

        return messages
