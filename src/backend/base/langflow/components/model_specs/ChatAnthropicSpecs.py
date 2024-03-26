from typing import Callable, Optional, Union

from langchain_community.chat_models.anthropic import ChatAnthropic
from pydantic.v1.types import SecretStr

from langflow.field_typing import BaseLanguageModel
from langflow.interface.custom.custom_component import CustomComponent


class ChatAnthropicComponent(CustomComponent):
    display_name = "ChatAnthropic"
    description = "`Anthropic` chat large language models."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/chat/integrations/anthropic"
    icon = "Anthropic"

    def build_config(self):
        return {
            "anthropic_api_key": {
                "display_name": "Anthropic API Key",
                "field_type": "str",
                "password": True,
            },
            "anthropic_api_url": {
                "display_name": "Anthropic API URL",
                "field_type": "str",
            },
            "model_kwargs": {
                "display_name": "Model Kwargs",
                "field_type": "dict",
                "advanced": True,
            },
            "temperature": {
                "display_name": "Temperature",
                "field_type": "float",
            },
        }

    def build(
        self,
        anthropic_api_key: str,
        anthropic_api_url: Optional[str] = None,
        model_kwargs: dict = {},
        temperature: Optional[float] = None,
    ) -> Union[BaseLanguageModel, Callable]:
        return ChatAnthropic(
            anthropic_api_key=SecretStr(anthropic_api_key),
            anthropic_api_url=anthropic_api_url,
            model_kwargs=model_kwargs,
            temperature=temperature,
        )
