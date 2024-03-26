from langchain_community.llms.cohere import Cohere
from langchain_core.language_models.base import BaseLanguageModel

from langflow.interface.custom.custom_component import CustomComponent


class CohereComponent(CustomComponent):
    display_name = "Cohere"
    description = "Cohere large language models."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/llms/integrations/cohere"
    icon = "Cohere"

    def build_config(self):
        return {
            "cohere_api_key": {"display_name": "Cohere API Key", "type": "password", "password": True},
            "max_tokens": {"display_name": "Max Tokens", "default": 256, "type": "int", "show": True},
            "temperature": {"display_name": "Temperature", "default": 0.75, "type": "float", "show": True},
        }

    def build(
        self,
        cohere_api_key: str,
        max_tokens: int = 256,
        temperature: float = 0.75,
    ) -> BaseLanguageModel:
        return Cohere(cohere_api_key=cohere_api_key, max_tokens=max_tokens, temperature=temperature)  # type: ignore
