
from langflow import CustomComponent
from langchain_core.language_models.base import BaseLanguageModel
from typing import Optional
from langchain_community.llms.cohere import Cohere

class CohereComponent(CustomComponent):
    display_name = "Cohere"
    description = "Cohere large language models."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/llms/integrations/cohere"

    def build_config(self):
        return {
            "cohere_api_key": {
                "display_name": "Cohere API Key",
                "type": "password",
                "password": True
            },
            "max_tokens": {
                "display_name": "Max Tokens",
                "default": 256,
                "type": "int",
                "show": True
            },
            "temperature": {
                "display_name": "Temperature",
                "default": 0.75,
                "type": "float",
                "show": True
            },
        }

    def build(
        self,
        cohere_api_key: str,
        max_tokens: Optional[int] = 256,
        temperature: Optional[float] = 0.75,
    ) -> BaseLanguageModel:
        return Cohere(cohere_api_key=cohere_api_key, max_tokens=max_tokens, temperature=temperature)
