from typing import Callable, Optional, Union

from langchain_anthropic import ChatAnthropic
from pydantic.v1.types import SecretStr

from langflow import CustomComponent
from langflow.field_typing import BaseLanguageModel


class ChatAnthropicComponent(CustomComponent):
    display_name = "ChatAnthropic"
    description = "`Anthropic` chat large language models."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/chat/integrations/anthropic"

    def build_config(self):
        return {
            "anthropic_api_key": {
                "display_name": "Anthropic API Key",
                "field_type": "str",
                "password": True,
            },
            "model_kwargs": {
                "display_name": "Model Kwargs",
                "field_type": "dict",
                "advanced": True,
            },
            "model_name": {
                "display_name": "Model Name",
                "field_type": "str",
                "advanced": False,
                "required": False,
                "options": ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
            },
            "temperature": {
                "display_name": "Temperature",
                "field_type": "float",
            },
            "max_tokens": {
                "display_name": "Max Tokens",
                "field_type": "int",
                "advanced": False,
                "required": False,
            },
            "top_k": {"display_name": "Top K", "field_type": "int", "advanced": True},
            "top_p": {"display_name": "Top P", "field_type": "float", "advanced": True},
        }

    def build(
        self,
        anthropic_api_key: str,
        model_kwargs: dict = {},
        model_name: str = "claude-3-opus-20240229",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = 1024,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> Union[BaseLanguageModel, Callable]:
        return ChatAnthropic(
            anthropic_api_key=SecretStr(anthropic_api_key),
            model_kwargs=model_kwargs,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,  # type: ignore
            top_k=top_k,
            top_p=top_p,
        )
