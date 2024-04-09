from typing import Optional

from langchain_anthropic import ChatAnthropic
from pydantic.v1.types import SecretStr


from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel


class AnthropicLLM(CustomComponent):
    display_name: str = "Anthropic"
    description: str = "Generate text using Anthropic Chat&Completion LLMs."
    icon = "Anthropic"

    field_order = [
        "model",
        "anthropic_api_key",
        "max_tokens",
        "temperature",
        "anthropic_api_url",
    ]

    def build_config(self):
        return {
            "model": {
                "display_name": "Model Name",
                "options": [
                    "claude-3-opus-20240229",
                    "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307",
                    "claude-2.1",
                    "claude-2.0",
                    "claude-instant-1.2",
                    "claude-instant-1",
                ],
                "info": "Name of the model to use.",
                "required": True,
                "value": "claude-3-opus-20240229",
            },
            "anthropic_api_key": {
                "display_name": "Anthropic API Key",
                "required": True,
                "password": True,
                "info": "Your Anthropic API key.",
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
            "anthropic_api_url": {
                "display_name": "Anthropic API URL",
                "advanced": True,
                "info": "Endpoint of the Anthropic API. Defaults to 'https://api.anthropic.com' if not specified.",
            },
            "code": {"show": False},
        }

    def build(
        self,
        model: str,
        anthropic_api_key: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        anthropic_api_url: Optional[str] = None,
    ) -> BaseLanguageModel:
        # Set default API endpoint if not provided
        if not anthropic_api_url:
            anthropic_api_url = "https://api.anthropic.com"

        try:
            output = ChatAnthropic(
                model_name=model,
                anthropic_api_key=(SecretStr(anthropic_api_key) if anthropic_api_key else None),
                max_tokens_to_sample=max_tokens,  # type: ignore
                temperature=temperature,
                anthropic_api_url=anthropic_api_url,
            )
        except Exception as e:
            raise ValueError("Could not connect to Anthropic API.") from e

        return output
