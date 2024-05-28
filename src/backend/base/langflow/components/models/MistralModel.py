from typing import Optional

from langchain_mistralai import ChatMistralAI
from pydantic.v1 import SecretStr

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Text


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
                "info": "The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
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
                    "mistral-large-latest",
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
            "max_retries": {
                "display_name": "Max Retries",
                "advanced": True,
            },
            "timeout": {
                "display_name": "Timeout",
                "advanced": True,
            },
            "max_concurrent_requests": {
                "display_name": "Max Concurrent Requests",
                "advanced": True,
            },
            "top_p": {
                "display_name": "Top P",
                "advanced": True,
            },
            "random_seed": {
                "display_name": "Random Seed",
                "advanced": True,
            },
            "safe_mode": {
                "display_name": "Safe Mode",
                "advanced": True,
            },
        }

    def build(
        self,
        input_value: Text,
        mistral_api_key: str,
        model_name: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = 256,
        mistral_api_base: Optional[str] = None,
        stream: bool = False,
        system_message: Optional[str] = None,
        max_retries: int = 5,
        timeout: int = 120,
        max_concurrent_requests: int = 64,
        top_p: float = 1,
        random_seed: Optional[int] = None,
        safe_mode: bool = False,
    ) -> Text:
        if not mistral_api_base:
            mistral_api_base = "https://api.mistral.ai"
        if mistral_api_key:
            api_key = SecretStr(mistral_api_key)
        else:
            api_key = None

        chat_model = ChatMistralAI(
            max_tokens=max_tokens or None,
            model_name=model_name,
            endpoint=mistral_api_base,
            api_key=api_key,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
            max_concurrent_requests=max_concurrent_requests,
            top_p=top_p,
            random_seed=random_seed,
            safe_mode=safe_mode,
        )

        return self.get_chat_result(chat_model, stream, input_value, system_message)
