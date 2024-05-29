from typing import Optional

from langchain_cohere import ChatCohere
from langchain_core.language_models.base import BaseLanguageModel
from pydantic.v1 import SecretStr

from langflow.custom import CustomComponent


class CohereComponent(CustomComponent):
    display_name = "Cohere"
    description = "Cohere large language models."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/llms/integrations/cohere"
    icon = "Cohere"

    def build_config(self):
        return {
            "cohere_api_key": {"display_name": "Cohere API Key", "type": "password", "password": True},
            "max_tokens": {
                "display_name": "Max Tokens",
                "advanced": True,
                "info": "The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
            },
            "temperature": {"display_name": "Temperature", "default": 0.75, "type": "float", "show": True},
        }

    def build(
        self,
        cohere_api_key: str,
        max_tokens: Optional[int] = 256,
        temperature: float = 0.75,
    ) -> BaseLanguageModel:
        if cohere_api_key:
            api_key = SecretStr(cohere_api_key)
        else:
            api_key = None
        return ChatCohere(cohere_api_key=api_key, max_tokens=max_tokens or None, temperature=temperature)  # type: ignore
