from typing import Optional

from langchain_mistralai import ChatMistralAI
from pydantic.v1 import SecretStr

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import NestedDict, Text


class MistralAIModelComponent(LCModelComponent):
    display_name = "MistralAI"
    description = "Generates text using MistralAI LLMs."
    icon = "MistralAI"

    field_order = [
        "max_tokens",
        "model_kwargs",
        "model_name",
        "mistral_api_base",
        "mistral_api_key",
        "temperature",
        "input_value",
        "system_message",
        "stream",
    ]

    def build_config(self):
        return {
            "input_value": {"display_name": "Input"},
            "max_tokens": {
                "display_name": "Max Tokens",
                "advanced": True,
            },
            "model_kwargs": {
                "display_name": "Model Kwargs",
                "advanced": True,
            },
            "model_name": {
                "display_name": "Model Name",
                "advanced": False,
                "options": [
                    "open-mistral-7b",
                    "open-mixtral-8x7b",
                    "open-mixtral-8x22b",
                    "mistral-small-latest",
                    "mistral-medium-latest",
                    "mistral-large-latest"
                ],
                "value": "open-mistral-7b",
            },
            "mistral_api_base": {
                "display_name": "Mistral API Base",
                "advanced": True,
                "info": (
                    "The base URL of the Mistral API. Defaults to https://api.mistral.ai.\n\n"
                    "You can change this to use other APIs like JinaChat, LocalAI and Prem."
                ),
            },
            "mistral_api_key": {
                "display_name": "Mistral API Key",
                "info": "The Mistral API Key to use for the Mistral model.",
                "advanced": False,
                "password": True,
            },
            "temperature": {
                "display_name": "Temperature",
                "advanced": False,
                "value": 0.1,
            },
            "stream": {
                "display_name": "Stream",
                "info": STREAM_INFO_TEXT,
                "advanced": True,
            },
            "system_message": {
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "advanced": True,
            },
        }

    def build(
        self,
        input_value: Text,
        mistral_api_key: str,
        temperature: float,
        model_name: str,
        max_tokens: Optional[int] = 256,
        model_kwargs: NestedDict = {},
        mistral_api_base: Optional[str] = None,
        stream: bool = False,
        system_message: Optional[str] = None,
    ) -> Text:
        if not mistral_api_base:
            mistral_api_base = "https://api.mistral.ai"
        if mistral_api_key:
            api_key = SecretStr(mistral_api_key)
        else:
            api_key = None

        chat_model = ChatMistralAI(
            max_tokens=max_tokens,
            model_kwargs=model_kwargs,
            model=model_name,
            base_url=mistral_api_base,
            api_key=api_key,
            temperature=temperature,
        )

        return self.get_chat_result(chat_model, stream, input_value, system_message)
