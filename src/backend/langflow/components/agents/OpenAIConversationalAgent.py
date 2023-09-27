from langflow import CustomComponent
from typing import Optional
from langchain.prompts import SystemMessagePromptTemplate
from langchain.tools import Tool
from langchain.schema.memory import BaseMemory
from langchain.chat_models import ChatOpenAI

from langchain.agents.agent import AgentExecutor
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.memory.token_buffer import ConversationTokenBufferMemory
from langchain.prompts.chat import MessagesPlaceholder
from langchain.agents.agent_toolkits.conversational_retrieval.openai_functions import (
    _get_default_system_message,
)


class ConversationalAgent(CustomComponent):
    display_name: str = "OpenAI Conversational Agent"
    description: str = "Conversational Agent that can use OpenAI's function calling API"

    def build_config(self):
        openai_function_models = [
            "gpt-3.5-turbo-0613",
            "gpt-3.5-turbo-16k-0613",
            "gpt-4-0613",
            "gpt-4-32k-0613",
        ]
        return {
            "tools": {"is_list": True, "display_name": "Tools"},
            "memory": {"display_name": "Memory"},
            "system_message": {"display_name": "System Message"},
            "max_token_limit": {"display_name": "Max Token Limit"},
            "model_name": {
                "display_name": "Model Name",
                "options": openai_function_models,
                "value": openai_function_models[0],
            },
            "code": {"show": False},
        }

    def build(
        self,
        model_name: str,
        openai_api_key: str,
        tools: Tool,
        openai_api_base: Optional[str] = None,
        memory: Optional[BaseMemory] = None,
        system_message: Optional[SystemMessagePromptTemplate] = None,
        max_token_limit: int = 2000,
    ) -> AgentExecutor:
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=openai_api_key,
            openai_api_base=openai_api_base,
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
            llm=llm, tools=tools, prompt=prompt  # type: ignore
        )
        return AgentExecutor(
            agent=agent,
            tools=tools,  # type: ignore
            memory=memory,
            verbose=True,
            return_intermediate_steps=True,
        )
