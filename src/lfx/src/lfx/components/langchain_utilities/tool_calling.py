from langchain.agents import create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate

from lfx.base.agents.agent import LCToolsAgentComponent

# IBM Granite-specific logic is in a separate file
from lfx.components.langchain_utilities.ibm_granite_handler import (
    create_granite_agent,
    get_enhanced_system_prompt,
    is_granite_model,
)
from lfx.inputs.inputs import (
    DataInput,
    HandleInput,
    MessageTextInput,
)
from lfx.schema.data import Data


class ToolCallingAgentComponent(LCToolsAgentComponent):
    display_name: str = "Tool Calling Agent"
    description: str = "An agent designed to utilize various tools seamlessly within workflows."
    icon = "LangChain"
    name = "ToolCallingAgent"

    inputs = [
        *LCToolsAgentComponent.get_base_inputs(),
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True,
            info="Language model that the agent utilizes to perform tasks effectively.",
        ),
        MessageTextInput(
            name="system_prompt",
            display_name="System Prompt",
            info="System prompt to guide the agent's behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
        ),
        DataInput(
            name="chat_history",
            display_name="Chat Memory",
            is_list=True,
            advanced=True,
            info="This input stores the chat history, allowing the agent to remember previous conversations.",
        ),
    ]

    def get_chat_history_data(self) -> list[Data] | None:
        return self.chat_history

    def create_agent_runnable(self):
        messages = []

        # Use local variable to avoid mutating component state on repeated calls
        effective_system_prompt = self.system_prompt or ""

        # Enhance prompt for IBM Granite models (they need explicit tool usage instructions)
        if is_granite_model(self.llm) and self.tools:
            effective_system_prompt = get_enhanced_system_prompt(effective_system_prompt, self.tools)
            # Store enhanced prompt for use in agent.py without mutating original
            self._effective_system_prompt = effective_system_prompt

        # Only include system message if system_prompt is provided and not empty
        if effective_system_prompt.strip():
            messages.append(("system", "{system_prompt}"))

        messages.extend(
            [
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )

        prompt = ChatPromptTemplate.from_messages(messages)
        self.validate_tool_names()

        try:
            # Use IBM Granite-specific agent if detected
            # Other WatsonX models (Llama, Mistral, etc.) use default behavior
            if is_granite_model(self.llm) and self.tools:
                return create_granite_agent(self.llm, self.tools, prompt)

            # Default behavior for other models (including non-Granite WatsonX models)
            return create_tool_calling_agent(self.llm, self.tools or [], prompt)
        except NotImplementedError as e:
            message = f"{self.display_name} does not support tool calling. Please try using a compatible model."
            raise NotImplementedError(message) from e
