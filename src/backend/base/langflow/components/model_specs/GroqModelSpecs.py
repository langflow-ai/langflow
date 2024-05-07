from typing import Optional

from langchain_groq import ChatGroq
from pydantic.v1 import SecretStr

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.groq_constants import MODEL_NAMES
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import BaseLanguageModel


class GroqModelSpecs(LCModelComponent):
    display_name: str = "Groq"
    description: str = "Generate text using Groq."
    icon = "Groq"

    field_order = [
        "groq_api_key",
        "model",
        "max_output_tokens",
        "temperature",
        "top_k",
        "top_p",
        "n",
        "input_value",
        "system_message",
        "stream",
    ]

    def build_config(self):
        return {
            "groq_api_key": {
                "display_name": "Groq API Key",
                "info": "API key for the Groq API.",
                "password": True,
            },
            "groq_api_base": {
                "display_name": "Groq API Base",
                "info": "Base URL path for API requests, leave blank if not using a proxy or service emulator.",
                "advanced": True,
            },
            "max_tokens": {
                "display_name": "Max Output Tokens",
                "info": "The maximum number of tokens to generate.",
                "advanced": True,
            },
            "temperature": {
                "display_name": "Temperature",
                "info": "Run inference with this temperature. Must by in the closed interval [0.0, 1.0].",
            },
            "n": {
                "display_name": "N",
                "info": "Number of chat completions to generate for each prompt. Note that the API may not return the full n completions if duplicates are generated.",
                "advanced": True,
            },
            "model_name": {
                "display_name": "Model",
                "info": "The name of the model to use. Supported examples: gemini-pro",
                "options": MODEL_NAMES,
            },
            "stream": {
                "display_name": "Stream",
                "info": STREAM_INFO_TEXT,
                "advanced": True,
            },
        }

    def build(
        self,
        groq_api_key: str,
        model_name: str,
        groq_api_base: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.1,
        n: Optional[int] = 1,
        stream: bool = False,
    ) -> BaseLanguageModel:
        return ChatGroq(
            model_name=model_name,
            max_tokens=max_tokens or None,  # type: ignore
            temperature=temperature,
            groq_api_base=groq_api_base,
            n=n or 1,
            groq_api_key=SecretStr(groq_api_key),
            streaming=stream,
        )
