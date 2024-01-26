from typing import Optional

from langchain_community.llms.anthropic import Anthropic
from pydantic.v1 import SecretStr

from langflow import CustomComponent
from langflow.field_typing import BaseLanguageModel, NestedDict


class AnthropicComponent(CustomComponent):
    display_name = "Anthropic"
    description = "Anthropic large language models."

    def build_config(self):
        return {
            "anthropic_api_key": {
                "display_name": "Anthropic API Key",
                "type": str,
                "password": True,
            },
            "anthropic_api_url": {
                "display_name": "Anthropic API URL",
                "type": str,
            },
            "model_kwargs": {
                "display_name": "Model Kwargs",
                "field_type": "NestedDict",
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
        anthropic_api_url: str,
        model_kwargs: NestedDict = {},
        temperature: Optional[float] = None,
    ) -> BaseLanguageModel:
        return Anthropic(
            anthropic_api_key=SecretStr(anthropic_api_key),
            anthropic_api_url=anthropic_api_url,
            model_kwargs=model_kwargs,
            temperature=temperature,
        )
