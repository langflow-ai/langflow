from typing import List, Optional

from langchain.agents.agent import AgentExecutor
from langchain.agents.agent_toolkits.conversational_retrieval.openai_functions import _get_default_system_message
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.chat_models import ChatOpenAI
from langchain.memory.token_buffer import ConversationTokenBufferMemory
from langchain.prompts import SystemMessagePromptTemplate
from langchain.prompts.chat import MessagesPlaceholder
from langchain.schema.memory import BaseMemory
from langchain.tools import Tool

from langflow import CustomComponent
from langflow.field_typing.range_spec import RangeSpec


class ConversationalAgent(CustomComponent):
    display_name: str = "OpenAI Conversational Agent"
    description: str = "Conversational Agent that can use OpenAI's function calling API"

    def build_config(self):
        openai_function_models = [
            "gpt-4-1106-preview",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "gpt-4",
            "gpt-4-32k",
        ]
        return {
            "tools": {"display_name": "Tools"},
            "memory": {"display_name": "Memory"},
            "system_message": {"display_name": "System Message"},
            "max_token_limit": {"display_name": "Max Token Limit"},
            "model_name": {
                "display_name": "Model Name",
                "options": openai_function_models,
                "value": openai_function_models[0],
            },
            "code": {"show": False},
            "temperature": {
                "display_name": "Temperature",
                "value": 0.2,
                "range_spec": RangeSpec(min=0, max=2, step=0.1),
            },
        }

    def build(
        self,
        model_name: str,
        openai_api_key: str,
        tools: List[Tool],
        openai_api_base: Optional[str] = None,
        memory: Optional[BaseMemory] = None,
        system_message: Optional[SystemMessagePromptTemplate] = None,
        max_token_limit: int = 2000,
        temperature: float = 0.9,
    ) -> AgentExecutor:
        llm = ChatOpenAI(
            model=model_name,
            api_key=openai_api_key,
            base_url=openai_api_base,
            max_tokens=max_token_limit,
            temperature=temperature,
        )
        if not memory:
            memory_key = "chat_history"
            memory = ConversationTokenBufferMemory(
                memory_key=memory_key,
                return_messages=True,
                output_key="output",
                llm=llm,
                max_token_limit=max_token_limit,
            )
        else:
            memory_key = memory.memory_key  # type: ignore

        _system_message = system_message or _get_default_system_message()
        prompt = OpenAIFunctionsAgent.create_prompt(
            system_message=_system_message,  # type: ignore
            extra_prompt_messages=[MessagesPlaceholder(variable_name=memory_key)],
        )
        agent = OpenAIFunctionsAgent(
            llm=llm,
            tools=tools,
            prompt=prompt,  # type: ignore
        )
        return AgentExecutor(
            agent=agent,
            tools=tools,  # type: ignore
            memory=memory,
            verbose=True,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
        )
