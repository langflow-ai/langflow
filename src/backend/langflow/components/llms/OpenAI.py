from typing import Dict, Optional

from langchain_openai.llms.base import OpenAI

from langflow import CustomComponent


class OpenAIComponent(CustomComponent):
    display_name = "OpenAI"
    description = "OpenAI large language models."

    def build_config(self):
        return {
            "max_tokens": {"display_name": "Max Tokens", "default": 256},
            "model_kwargs": {"display_name": "Model Kwargs", "advanced": True},
            "model_name": {
                "display_name": "Model Name",
                "value": "text-davinci-003",
                "options": [
                    "text-davinci-003",
                    "text-davinci-002",
                    "text-curie-001",
                    "text-babbage-001",
                    "text-ada-001",
                ],
            },
            "openai_api_base": {
                "display_name": "OpenAI API Base",
                "info": (
                    "The base URL of the OpenAI API. Defaults to https://api.openai.com/v1.\n"
                    "You can change this to use other APIs like JinaChat, LocalAI and Prem."
                ),
            },
            "openai_api_key": {
                "display_name": "OpenAI API Key",
                "value": "",
                "password": True,
            },
            "temperature": {"display_name": "Temperature", "value": 0.7},
        }

    def build(
        self,
        max_tokens: Optional[int] = 256,
        model_kwargs: Optional[Dict] = None,
        model_name: str = "text-davinci-003",
        openai_api_base: Optional[str] = "",
        openai_api_key: str = "",
        temperature: Optional[float] = 0.7,
    ) -> OpenAI:
        if not openai_api_base:
            openai_api_base = "https://api.openai.com/v1"
        return OpenAI(
            max_tokens=max_tokens,
            model_kwargs=model_kwargs or {},
            model_name=model_name,
            openai_api_base=openai_api_base,
            openai_api_key=openai_api_key,
            temperature=temperature,
        )
