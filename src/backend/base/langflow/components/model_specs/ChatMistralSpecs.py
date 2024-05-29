from typing import Optional

from langchain_mistralai import ChatMistralAI
from pydantic.v1 import SecretStr

from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel


class MistralAIModelComponent(CustomComponent):
    display_name: str = "MistralAI"
    description: str = "Generate text using MistralAI LLMs."
    icon = "MistralAI"

    field_order = [
        "model",
        "mistral_api_key",
        "max_tokens",
        "temperature",
        "mistral_api_base",
    ]

    def build_config(self):
        return {
            "model": {
                "display_name": "Model Name",
                "options": [
                    "open-mistral-7b",
                    "open-mixtral-8x7b",
                    "open-mixtral-8x22b",
                    "mistral-small-latest",
                    "mistral-medium-latest",
                    "mistral-large-latest",
                ],
                "info": "Name of the model to use.",
                "required": True,
                "value": "open-mistral-7b",
            },
            "mistral_api_key": {
                "display_name": "Mistral API Key",
                "required": True,
                "password": True,
                "info": "Your Mistral API key.",
            },
            "max_tokens": {
                "display_name": "Max Tokens",
                "field_type": "int",
                "advanced": True,
                "value": 256,
            },
            "temperature": {
                "display_name": "Temperature",
                "field_type": "float",
                "value": 0.1,
            },
            "mistral_api_base": {
                "display_name": "Mistral API Base",
                "advanced": True,
                "info": "Endpoint of the Mistral API. Defaults to 'https://api.mistral.ai' if not specified.",
            },
            "code": {"show": False},
        }

    def build(
        self,
        model: str,
        temperature: float = 0.1,
        mistral_api_key: Optional[str] = None,
        max_tokens: Optional[int] = None,
        mistral_api_base: Optional[str] = None,
    ) -> BaseLanguageModel:
        # Set default API endpoint if not provided
        if not mistral_api_base:
            mistral_api_base = "https://api.mistral.ai"

        try:
            output = ChatMistralAI(
                model_name=model,
                api_key=(SecretStr(mistral_api_key) if mistral_api_key else None),
                max_tokens=max_tokens or None,
                temperature=temperature,
                endpoint=mistral_api_base,
            )
        except Exception as e:
            raise ValueError("Could not connect to Mistral API.") from e

        return output
