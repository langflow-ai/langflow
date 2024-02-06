from typing import Optional, Union

from langchain.llms import BaseLLM
from langchain_community.chat_models.openai import ChatOpenAI

from langflow import CustomComponent
from langflow.field_typing import BaseLanguageModel, NestedDict


class ChatOpenAIComponent(CustomComponent):
    display_name = "ChatOpenAI"
    description = "`OpenAI` Chat large language models API."

    def build_config(self):
        return {
            "max_tokens": {
                "display_name": "Max Tokens",
                "field_type": "int",
                "advanced": False,
                "required": False,
            },
            "model_kwargs": {
                "display_name": "Model Kwargs",
                "field_type": "NestedDict",
                "advanced": True,
                "required": False,
            },
            "model_name": {
                "display_name": "Model Name",
                "field_type": "str",
                "advanced": False,
                "required": False,
                "options": [
                    "gpt-4-turbo-preview",
                    "gpt-4-0125-preview",
                    "gpt-4-1106-preview",
                    "gpt-4-vision-preview",
                    "gpt-3.5-turbo-0125",
                    "gpt-3.5-turbo-1106",
                ],
            },
            "openai_api_base": {
                "display_name": "OpenAI API Base",
                "field_type": "str",
                "advanced": False,
                "required": False,
                "info": (
                    "The base URL of the OpenAI API. Defaults to https://api.openai.com/v1.\n\n"
                    "You can change this to use other APIs like JinaChat, LocalAI and Prem."
                ),
            },
            "openai_api_key": {
                "display_name": "OpenAI API Key",
                "field_type": "str",
                "advanced": False,
                "required": False,
                "password": True,
            },
            "temperature": {
                "display_name": "Temperature",
                "field_type": "float",
                "advanced": False,
                "required": False,
                "value": 0.7,
            },
        }

    def build(
        self,
        max_tokens: Optional[int] = 256,
        model_kwargs: NestedDict = {},
        model_name: str = "gpt-4-1106-preview",
        openai_api_base: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Union[BaseLanguageModel, BaseLLM]:
        if not openai_api_base:
            openai_api_base = "https://api.openai.com/v1"
        return ChatOpenAI(
            max_tokens=max_tokens,
            model_kwargs=model_kwargs,
            model=model_name,
            base_url=openai_api_base,
            api_key=openai_api_key,
            temperature=temperature,
        )
